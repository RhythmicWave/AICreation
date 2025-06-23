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
        return image, audio

    async def _process_segment(self, subdir: str, temp_dir: str, settings: Dict) -> Optional[str]:
        """处理单个视频片段"""
        temp_file = os.path.join(temp_dir, f"vid_{subdir}_{os.getpid()}.mp4")
        start_time = time.time()
        frames = []

        try:
            # 在线程中加载资源
            loop = asyncio.get_running_loop()
            image, audio = await loop.run_in_executor(
                None, 
                lambda: self._load_resources(os.path.join(settings['chapter_path'], subdir), settings['resolution'])
            )
            
            duration = audio.duration
            total_frames = int(duration * settings['fps'])

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
                lambda: self._write_temp_video(frames, audio, temp_file, settings)
            )
            
            logger.info("完成片段 %s | 耗时: %.1fs | 大小: %.1fMB", 
                       subdir, time.time()-start_time, os.path.getsize(temp_file)/1024/1024)
            
            # 更新进度
            with self.task_lock:
                self.progress += 1
                
            return temp_file

        except Exception as e:
            logger.error("处理失败 [%s]: %s", subdir, str(e))
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return None
        finally:
            # 释放资源
            if 'image' in locals():
                image.close()
            if 'audio' in locals():
                audio.close()
            del frames
            gc.collect()

    def _write_temp_video(self, frames: list, audio: AudioFileClip, output_path: str, settings: Dict):
        """
        安全写入视频片段
        使用临时文件来暂存，避免内存占用过高
        """
        with ImageSequenceClip(frames, fps=settings['fps']) as video_clip:
            # 确保音频时长与视频对齐
            if audio.duration > video_clip.duration:
                audio = audio.subclipped(0, video_clip.duration)
            elif audio.duration < video_clip.duration:
                # 若音频短于视频，则静音填充
                from numpy import zeros
                silence = AudioArrayClip(
                    zeros((1, int(audio.fps * (video_clip.duration - audio.duration)))), 
                    fps=audio.fps
                )
                silence = silence.with_start(audio.duration)
                audio = CompositeAudioClip([audio, silence])

            # 绑定音频
            final_clip = video_clip.with_audio(audio)

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
                threads=settings.get('threads', 4),
                ffmpeg_params=ffmpeg_params,
                logger=None
            )

    async def generate_video(self, chapter_path: str, video_settings: Dict = None) -> str:
        """生成视频主流程"""
        self.stop_flag.clear()
        final_settings = {**self.default_settings, **(video_settings or {})}
        
        final_settings['chapter_path'] = chapter_path
        output_path = os.path.join(chapter_path, "video.mp4")
        temp_files = []
   
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
                
                # 等待当前批次完成
                batch_results = await asyncio.gather(*tasks)
                
                # 收集结果
                valid_results = [r for r in batch_results if r]
                temp_files.extend(valid_results)
                
                # 检查是否取消
                if self.stop_flag.is_set():
                    await self._cleanup_temp_files_async(temp_files)
                    logger.info("视频生成被用户取消")
                    raise ValueError("视频生成被用户取消")
                        
            # 合并临时文件
            if not temp_files:
                raise ValueError("没有生成有效视频片段")
                
            # 更新进度状态为合并阶段
            with self.task_lock:
                self.current_task = "合并视频中"
            
            # 执行合并
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._merge_videos(temp_files, output_path, final_settings)
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
            if temp_files:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: self._cleanup_temp_files(temp_files))

    def _merge_videos(self, temp_files: List[str], output_path: str, settings: Dict) -> str:
        """合并视频片段"""
        concat_list = os.path.join(os.path.dirname(output_path), "concat.txt")
       
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
                '-y', output_path
            ]
            if settings.get('use_cuda', False) and self.cuda_available:
                cmd[1:1] = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
      
            # 执行命令
            subprocess.run(cmd, check=True, capture_output=True)
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
            if os.path.exists(concat_list):
                os.remove(concat_list)

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
        """清理临时文件"""
        for f_path in files:
            try:
                if os.path.exists(f_path):
                    os.remove(f_path)
                    logger.debug("已清理: %s", f_path)
            except Exception as e:
                logger.warning("清理失败 %s: %s", f_path, str(e))
                
    async def _cleanup_temp_files_async(self, files: List[str]):
        """异步清理临时文件"""
        if not files:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self._cleanup_temp_files(files))