import asyncio
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from typing import Optional, Tuple, Dict
import os
from pathlib import Path
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from server.config.config import load_config
from server.services.video_service import VideoService
from server.utils.response import make_response, APIException
import logging
from PIL import Image

router = APIRouter(prefix='/video')
logger = logging.getLogger(__name__)

# 创建视频服务的全局单例实例
video_service = VideoService()

class VideoSettings(BaseModel):
    project_name:Optional[str] = None
    chapter_name:Optional[str] = None
    """视频效果配置模型"""
    fade_duration: Optional[float] = 1# 淡入淡出时长（秒）
    fps: Optional[float] = 20
    use_pan: Optional[bool] = True#是否使用镜头平移效果
    pan_range: Optional[Tuple[float, float]] = (0.5, 0.5)# 横向移动原图可用范围的50%，纵向50%
    resolution: Optional[Tuple[int, int]] = (1600, 900)

@router.post("/generate_video")
async def generate_video(settings: Optional[VideoSettings] = None):
    try:
        config = load_config()
        base_path = config.get('projects_path', 'projects/')
        chapter_path = os.path.join(base_path, settings.project_name, settings.chapter_name)
        
        if not os.path.exists(chapter_path):
            return make_response(status='error', msg='chapter不存在')


        output_path = await video_service.generate_video(
            str(chapter_path),
            video_settings=settings.model_dump(exclude_unset=True) if settings else None
        )

        return make_response(
            data={"video_path": output_path},
            msg="Video generated successfully"
        )
    except APIException as e:
        return make_response(status='error', msg=e.detail)
    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.get("/get_video")
async def get_video(project_name: str, chapter_name: str):
    """获取视频文件接口"""
    try:
        config = load_config()
        video_path = Path(config['projects_path']) / project_name / chapter_name / "video.mp4"
        
        if not video_path.exists():
            return make_response(status='error', msg='视频不存在')
            
        return FileResponse(
            video_path,
            media_type="video/mp4",
            filename=f"{chapter_name}_video.mp4"
        )
    except APIException as e:
        return make_response(status='error', msg=e.detail)
    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.get("/generation_progress")
async def get_generation_progress() -> Dict:
    """获取视频生成进度接口"""
    try:
        progress_data = video_service.get_progress()
        return make_response(
            data=progress_data,
            msg="Progress retrieved successfully"
        )
    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.post("/cancel_generation")
async def cancel_generation():
    """取消视频生成接口"""
    try:
        result = video_service.cancel_generation()
        return make_response(
            data={"cancelled": result},
            msg="Video generation cancelled"
        )
    except Exception as e:
        return make_response(status='error', msg=str(e))
