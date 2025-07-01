import logging
import os
import time
import numpy as np
import subprocess
import threading
import asyncio
import gc
from typing import List, Dict, Optional, Tuple
from PIL import Image
from moviepy import ImageSequenceClip, AudioFileClip, CompositeAudioClip, AudioArrayClip
from server.utils.image_effect import ImageEffects

logger = logging.getLogger(__name__)

class VideoService:
    """视频生成服务"""
    
    def __init__(self):
        self.default_settings = {
            'resolution': (1024, 1024),
            'fps': 20,
            'threads': max(2,os.cpu_count()//2),
            'use_cuda': True,
            'codec': 'h264_nvenc',
            'batch_size': max(2, os.cpu_count()//2),
            'fade_duration': 1,  # 淡入淡出时长（秒）
            'use_pan': True,
            'pan_range': (0.5, 0.5),  # 横向移动原图可用范围的50%，纵向50%
        }
        self.stop_flag = threading.Event()
        self.cuda_available = self._check_hardware()
        # 进度追踪
        self.progress = 0
        self.total_segments = 0
        self.current_task = None
        self.task_lock = threading.Lock()

    def _check_hardware(self) -> bool:
        """检查硬件编码支持"""
        try:
            result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
            cuda_available = 'h264_nvenc' in result.stdout
     
            if not cuda_available:
                logger.warning("NVENC不可用，切换至CPU模式")
                self.default_settings.update({
                    'use_cuda': False,
                })
            else:
                logger.info("NVENC可用，使用GPU模式")
            return cuda_available
        except Exception as e:
            logger.error("硬件检测失败: %s", str(e))
            return False

    def _load_resources(self, subdir_path: str, resolution: Tuple[int, int]) -> tuple:
        """加载图片和音频资源"""
        image_path = os.path.join(subdir_path, "image.png")
        audio_path = os.path.join(subdir_path, "audio.mp3")

        # 验证文件有效性
        for path in [image_path, audio_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"文件不存在: {path}")
            if os.path.getsize(path) < 1024:
                raise ValueError(f"文件过小: {path}")

        # 加载图片
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            image=img.copy()
            # image = img.resize(resolution, Image.LANCZOS)

        # 加载音频
        audio = AudioFileClip(audio_path)
        if audio.duration is None or audio.duration < 0.05:
            audio.close()  # 释放文件句柄
            raise ValueError(f"音频文件时长过短或无效: {audio_path}")
            
        return image, audio

    async def _process_segment(self, subdir: str, temp_dir: str, settings: Dict) -> Optional[Tuple[str, str]]:
        """处理单个视频片段"""
        # 增加subdir，进一步确保唯一性
        temp_file = os.path.join(temp_dir, f"vid_{subdir}_{os.getpid()}.mp4")
        temp_audio_path = os.path.join(
            os.path.dirname(temp_file), 
            f"temp_audio_{subdir}_{os.getpid()}_{time.time_ns()}.m4a"
        )
        start_time = time.time()
        frames = []
        image = None
        audio = None

        try:
            # 在线程中加载资源
            loop = asyncio.get_running_loop()
            image, audio = await loop.run_in_executor(
                None, 
                lambda: self._load_resources(os.path.join(settings['chapter_path'], subdir), settings['resolution'])
            )
            
            duration = audio.duration
            total_frames = int(duration * settings['fps'])
            if total_frames == 0:
                raise ValueError(f"计算的总帧数为0，视频时长过短。 Subdir: {subdir}")

            # 批量生成帧
            for i in range(total_frames):
                if self.stop_flag.is_set():
                    break
                # 线程处理图像
                frame = await loop.run_in_executor(
                    None,
                    lambda: self._apply_effects(image.copy(), i/settings['fps'], duration, settings, subdir)
                )
                frames.append(np.array(frame))
                frame.close()

            # 写入视频
            await loop.run_in_executor(
                None,
                lambda: self._write_temp_video(frames, audio, temp_file, temp_audio_path, settings)
            )
            
            logger.info("完成片段 %s | 耗时: %.1fs | 大小: %.1fMB", 
                       subdir, time.time()-start_time, os.path.getsize(temp_file)/1024/1024)
            
            # 更新进度
            with self.task_lock:
                self.progress += 1
                
            return temp_file, temp_audio_path

        finally:
            # 只释放内存资源，不再处理文件删除
            if image:
                image.close()
            if audio:
                audio.close()
            del frames
            gc.collect()

    def _write_temp_video(self, frames: list, audio: AudioFileClip, output_path: str, temp_audio_path: str, settings: Dict):
        """
        安全写入视频片段
        使用临时文件来暂存，避免内存占用过高
        """
        with ImageSequenceClip(frames, fps=settings['fps']) as video_clip:
            # 使用 .with_duration() 来精确、安全地对齐音视频时长
            # 这会优雅地处理时长不匹配问题，无论是填充静音还是截断
            final_audio = audio.with_duration(video_clip.duration)

            # 绑定音频
            final_clip = video_clip.with_audio(final_audio)

            # 设置编码参数
            ffmpeg_params = []
            if settings.get('use_cuda', False) and self.cuda_available:
                ffmpeg_params.extend(['-c:v', 'h264_nvenc', '-preset', 'medium', '-gpu', '0'])
            else:
                ffmpeg_params.extend(['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'])

            # 写入文件
            final_clip.write_videofile(
                output_path,
                codec=None,
                audio_codec='aac',
                temp_audiofile=temp_audio_path, # 明确指定临时音频文件路径
                threads=settings.get('threads', 4),
                ffmpeg_params=ffmpeg_params,
                logger=None
            )

    async def generate_video(self, chapter_path: str, video_settings: Dict = None) -> str:
        """生成视频主流程"""
        chapter_path = os.path.abspath(chapter_path)
        self.stop_flag.clear()
        final_settings = {**self.default_settings, **(video_settings or {})}
        
        final_settings['chapter_path'] = chapter_path
        output_path = os.path.join(chapter_path, "video.mp4")
        temp_video_files = []
        all_temp_files = []
   
        try:
            # 获取待处理片段列表
            subdirs = sorted([
                d for d in os.listdir(chapter_path)
                if os.path.isdir(os.path.join(chapter_path, d)) and d.isdigit()
            ], key=lambda x: int(x))
            
            if not subdirs:
                raise ValueError("无有效视频片段")

            # 初始化进度信息
            with self.task_lock:
                self.progress = 0
                self.total_segments = len(subdirs)
                self.current_task = f"{os.path.basename(chapter_path)}"
          
            logger.info("发现 %d 个待处理片段", len(subdirs))
            
            # 分批处理片段
            batch_size = final_settings.get('batch_size', 8)
            for i in range(0, len(subdirs), batch_size):
                batch = subdirs[i:i+batch_size]
                tasks = [self._process_segment(subdir, chapter_path, final_settings) for subdir in batch]
                
                # 等待当前批次完成，即使有异常也继续
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 收集结果并处理异常
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error("一个视频片段处理失败: %s", result)
                    elif result:
                        video_path, audio_path = result
                        temp_video_files.append(video_path)
                        all_temp_files.extend([video_path, audio_path])
                
                # 检查是否取消
                if self.stop_flag.is_set():
                    # 在finally中统一处理清理
                    logger.info("视频生成被用户取消")
                    raise ValueError("视频生成被用户取消")

            # 检查是否有任何片段失败
            if len(temp_video_files) != len(subdirs):
                 raise ValueError("部分视频片段生成失败，无法合并。请检查日志。")
                        
            # 合并临时文件
            if not temp_video_files:
                raise ValueError("没有生成有效视频片段")
                
            # 更新进度状态为合并阶段
            with self.task_lock:
                self.current_task = "合并视频中"
            
            # 执行合并
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._merge_videos(temp_video_files, output_path, final_settings)
            )
            
            # 标记完成
            with self.task_lock:
                self.current_task = "已完成"
                self.progress = self.total_segments
                
            return result

        except Exception as e:
            logger.error("视频生成失败: %s", str(e))
            raise
        finally:
            # 清理临时文件
            if all_temp_files:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._cleanup_temp_files, all_temp_files)

    def _merge_videos(self, temp_files: List[str], output_path: str, settings: Dict) -> str:
        """合并视频片段"""
        concat_list = os.path.join(os.path.dirname(output_path), "concat.txt")
        # 写入到一个临时文件，避免在合并过程中被读取
        # 通过在扩展名前插入标记来创建临时文件名，保留原始扩展名
        root, ext = os.path.splitext(output_path)
        temp_output_path = f"{root}.tmp_{os.getpid()}{ext}"
       
        try:
            # 生成合并列表
            with open(concat_list, 'w', encoding='utf-8') as f:
                for file in temp_files:
                    file_path = os.path.abspath(file).replace('\\', '/')
                    f.write(f"file '{file_path}'\n")
            
            # 构建FFmpeg命令
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list,
                '-c', 'copy',
                '-movflags', '+faststart',
                '-y', temp_output_path
            ]
            if settings.get('use_cuda', False) and self.cuda_available:
                cmd[1:1] = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
      
            # 执行命令
            subprocess.run(cmd, check=True, capture_output=True)
            
            # 原子化地替换/重命名文件
            os.replace(temp_output_path, output_path)

            logger.info("视频合并成功: %s", output_path)
            return output_path
            
        except subprocess.CalledProcessError as e:
            # 解码错误信息
            import locale
            encoding = locale.getpreferredencoding()
            error_msg = e.stderr.decode(encoding, errors='replace')
            logger.error("合并失败: %s", error_msg)
            raise
        finally:
            # 确保所有临时文件都被清理
            if os.path.exists(concat_list):
                os.remove(concat_list)
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)

    def _apply_effects(self, image: Image.Image, time_val: float, 
                      duration: float, settings: Dict, subdir: str) -> Image.Image:
        """应用视频特效"""
        try:
            effect_params = {
                'output_size': settings.get('resolution', self.default_settings['resolution']),
                'fade_duration': settings.get('fade_duration', 1.0),
                'use_pan': settings.get('use_pan', True),
                'pan_range': settings.get('pan_range', (0.5, 0)),
                'segment_index': int(subdir) if subdir.isdigit() else 0
            }
            
            return ImageEffects.apply_effects(
                image, time_val, duration, effect_params
            )
        except Exception as e:
            logger.error("特效处理失败: %s", str(e))
            raise

    def get_progress(self) -> Dict:
        """获取当前视频生成进度"""
        with self.task_lock:
            total = max(1, self.total_segments)
            percentage = int((self.progress / total) * 100)
            return {
                "progress": self.progress,
                "total": total,
                "percentage": percentage,
                "current_task": self.current_task
            }
            
    def cancel_generation(self) -> bool:
        """取消视频生成"""
        self.stop_flag.set()
        return True

    def _cleanup_temp_files(self, files: List[str]):
        """Robustly cleans up temporary files, with retries for locked files."""
        for f_path in files:
            if not os.path.exists(f_path):
                continue
            
            attempts = 3
            for i in range(attempts):
                try:
                    os.remove(f_path)
                    logger.debug("已清理: %s", f_path)
                    break  # Success
                except PermissionError as e:  # Specifically catch PermissionError for retries
                    if i < attempts - 1:
                        logger.warning("文件被占用，将在0.5秒后重试: %s. Error: %s", f_path, e)
                        time.sleep(0.5)
                    else:
                        logger.error("多次尝试后仍无法删除文件: %s. Error: %s", f_path, e)
                except Exception as e:
                    logger.error("清理临时文件时发生未知错误 %s: %s", f_path, str(e))
                    break  # Don't retry on other errors