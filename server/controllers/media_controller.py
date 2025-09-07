from fastapi import APIRouter, Depends, HTTPException, Request, Response,Body
from server.config.config import load_config, get_prompt_style_by_name
from server.services.image_service import ImageService
from server.services.audio_service import AudioService
from server.utils.response import make_response
import os
import datetime
import logging
from fastapi.responses import FileResponse
from fastapi import UploadFile, File, Form

config = load_config()
router = APIRouter(prefix='/media')
image_service = ImageService()
audio_service = AudioService()
logger = logging.getLogger(__name__)

@router.post('/generate_images')
async def generate_images(request: Request):
    """生成图片的接口。"""
    try:
        data = await request.json()
        
        # 获取项目、章节和提示词信息
        project_name = data.get('project_name')
        chapter_name = data.get('chapter_name')
        prompts = data.get('prompts')
        image_settings = data.get('imageSettings')
        
        reference_image_infos = data.get('reference_image_infos')
        
        
        
        if not all([project_name, chapter_name, prompts]):
            return make_response(status='error', msg='缺少必要参数：project_name, chapter_name, prompts')
        
        # 获取工作流和参数
        workflow = data.get('workflow', config.get('default_workflow', {}).get('name', 'default_workflow.json'))

        params = {}
        width = image_settings.get('width', 512)
        height = image_settings.get('height', 768)
        style = image_settings.get('style','sai-anime')
        

        style_template = "{prompt}"
        negative_prompt = ""
        if style:
             
            # 使用新函数获取风格
            style_data = get_prompt_style_by_name(style)

            # 如果未找到风格，返回错误
            if not style_data:
                return make_response(status='error', msg=f'未找到指定的风格: {style}')

            style_template = style_data.get('prompt')
            negative_prompt = style_data.get('negative_prompt', "")
        
        
        params['width']=width
        params['height']=height
        
        if negative_prompt:
            params['negative_prompt'] = negative_prompt
        
        reference_image_paths=[]
        if config['comfyui'].get('reference_image_mode', True) and reference_image_infos:
            for info in reference_image_infos:
                character1=info.get('character1','')
                character2=info.get('character2','')
                scene=info.get('scene','')
                path1=os.path.join(config['projects_path'],project_name,"Character",character1,"image.png") if character1 else ''
                path2=os.path.join(config['projects_path'],project_name,"Character",character2,"image.png") if character2 else ''
                path3=os.path.join(config['projects_path'],project_name,"Scene",scene,"image.png") if scene else ''
                reference_image_paths.append((path1,path2,path3))
                
            workflow="nunchaku-flux-kontext-multi-images.json"#当有参考图片时，使用这个工作流
            print(reference_image_paths)
            params['reference_image_paths']=reference_image_paths

        # 构建输出路径数组
        output_dirs = []
        processed_prompts = []
        for prompt_data in prompts:
            span_id = prompt_data.get('id')
            if span_id is None:
                span_id=''
                
            # 构建输出路径（确保与获取图片时的路径一致）
            span_path = os.path.join(config['projects_path'], project_name, chapter_name, str(span_id))
            output_dirs.append(span_path)
            
            # 确保目录存在
            os.makedirs(span_path, exist_ok=True)
            logger.info(f"Created output directory: {span_path}")

            # 获取原始提示词
            prompt_text = prompt_data.get('prompt', '')
            
            # 如果有风格模板，应用模板
            if style_template and '{prompt}' in style_template:
                processed_prompt = style_template.replace('{prompt}', prompt_text)
            else:
                processed_prompt = prompt_text
                
            processed_prompts.append(processed_prompt)

        # 提取所有提示词
        if not all(processed_prompts):
            return make_response(status='error', msg='prompts中存在空的prompt字段')
        
        try:
            # 调用图像服务生成图片
            result = image_service.generate_images(
                prompts=processed_prompts,
                output_dirs=output_dirs,
                workflow=workflow,
                params=params
            )
            return make_response(
                data=result,
                msg='图片生成任务已提交'
            )
        except Exception as e:
            print(f"Error : {str(e)}")
            return make_response(status='error', msg=str(e))
            
    except Exception as e:
        return make_response(status='error', msg=f'处理请求时发生错误：{str(e)}')

@router.post('/generate-audio')
async def generate_audio(request: Request):
    """生成音频文件的接口。"""
    try:
        data = await request.json()
        
        # 获取项目、章节和提示词信息
        project_name = data.get('project_name')
        chapter_name = data.get('chapter_name')
        prompts = data.get('prompts')
        audio_settings = data.get('audioSettings', {})
        
        if not all([project_name, chapter_name, prompts]):
            return make_response(status='error', msg='缺少必要参数：project_name, chapter_name, prompts')
        
        # 构建输出路径数组
        output_dirs = []
        prompt_texts = []
        for prompt_data in prompts:
            span_id = prompt_data.get('id')
            if span_id is None:
                return make_response(status='error', msg='prompts中缺少id字段')
                
            # 构建输出路径
            span_path = os.path.join(config['projects_path'], project_name, chapter_name, str(span_id))
            output_dirs.append(span_path)
            
            # 提取提示词文本
            prompt_text = prompt_data.get('prompt')
            if not prompt_text:
                return make_response(status='error', msg='prompts中存在空的prompt字段')
            prompt_texts.append(prompt_text)
        
        try:
            rate=audio_settings.get('rate', '+0%')
            if(rate=='0%'):
                rate='+0%'
            # 调用音频服务生成音频
            result = await audio_service.generate_audio(
                prompts=prompt_texts,
                output_dirs=output_dirs,
                voice=audio_settings.get('voice', 'zh-CN-XiaoxiaoNeural'),
                rate=rate
            )
            return make_response(
                data=result,
                msg='音频生成任务已提交'
            )
        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            return make_response(status='error', msg=str(e))
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return make_response(status='error', msg=f'处理请求时发生错误：{str(e)}')

@router.get('/progress')
async def get_generation_progress(task_id: str):
    """获取生成任务的进度。"""
    try:
        if not task_id:
            return make_response(status='error', msg='缺少任务ID')
            
        # 获取任务进度
        if task_id.startswith('audio_'):
            progress = audio_service.get_generation_progress(task_id)
            progress['task_type'] = 'audio'
        else:
            progress = image_service.get_generation_progress(task_id)
            progress['task_type'] = 'image'
            
        return make_response(
            data=progress,
            msg='获取进度成功'
        )
    except ValueError as e:
        return make_response(status='error', msg=str(e))
    except Exception as e:
        logger.error(f"Error getting progress: {str(e)}")
        return make_response(status='error', msg=f'获取进度时发生错误：{str(e)}')

@router.post('/cancel')
async def cancel_generation(request: Request):
    """取消生成任务。"""
    try:
        data=await request.json()
        task_id=data.get("task_id")
        print("准备中断：",task_id)
        # 根据任务ID的前缀判断是图片任务还是音频任务
        if task_id.startswith('audio_'):
            success = audio_service.cancel_generation(task_id)
        else:
            success = image_service.cancel_generation(task_id)
            
        if success:
            return make_response(msg='任务已取消')
        else:
            return make_response(status='error', msg='取消任务失败')
    except Exception as e:
        logger.error(f"Error cancelling task: {str(e)}")
        return make_response(status='error', msg=str(e))


@router.get('/workflows')
async def list_workflows():
    """列出所有可用的工作流。"""
    try:
        workflows = image_service.list_workflows()
        return make_response(
            data={'workflows': workflows},
            msg='获取工作流列表成功'
        )
    except Exception as e:
        return make_response(status='error', msg=f'获取工作流列表时发生错误：{str(e)}')

@router.get('/workflow/{workflow_name}')
async def get_workflow(workflow_name: str):
    """获取指定工作流的详细信息。"""
    try:
        workflow = image_service.get_workflow(workflow_name)
        if workflow is None:
            return make_response(status='error', msg='工作流不存在')
        return make_response(
            data={'workflow': workflow},
            msg='获取工作流成功'
        )
    except Exception as e:
        return make_response(status='error', msg=f'获取工作流时发生错误：{str(e)}')

@router.get('/get_image')
async def get_media_image(project_name: str, chapter_name: str, span_id: str):
    """获取指定项目章节span的图片。"""
    try:
        # 构建图片路径（与生成时的路径保持一致）
        image_path = os.path.join(config['projects_path'], project_name, chapter_name, str(span_id), 'image.png')
        logger.info(f"Trying to access image at: {image_path}")
            
        return FileResponse(image_path, media_type='image/png')
        
    except Exception as e:
        logger.error(f"Error accessing image: {str(e)}")
        return make_response(status='error', msg=str(e))

@router.get('/get_audio')
async def get_media_audio(project_name: str, chapter_name: str, span_id: str):
    """获取指定项目章节span的音频。"""
    try:
        # 构建音频路径
        audio_path = os.path.join(config['projects_path'], project_name, chapter_name, str(span_id), 'audio.mp3')
        
        if not os.path.exists(audio_path):
            return make_response(status='error', msg='音频不存在')
            
        return FileResponse(audio_path, media_type='audio/mpeg')
        
    except Exception as e:
        logger.error(f"Error accessing audio: {str(e)}")
        return make_response(status='error', msg=str(e))

@router.post('/upload_image')
async def upload_reference_image(
    project_name: str = Form(...),
    chapter_name: str = Form(...),
    span_id: str = Form(...),
    file: UploadFile = File(...)
):
    """上传参考图片，保存到与生成图片一致的路径：
    projects/{project_name}/{chapter_name}/{span_id}/image.png
    """
    try:
        if not all([project_name, chapter_name, span_id, file]):
            return make_response(status='error', msg='缺少必要参数：project_name, chapter_name, span_id, file')

        # 目标目录与文件
        target_dir = os.path.join(config['projects_path'], project_name, chapter_name, str(span_id))
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, 'image.png')

        # 读取上传内容
        content = await file.read()

        # 直接写入二进制，前端读取使用 image.png 路径
        with open(target_path, 'wb') as f:
            f.write(content)

        return make_response(data=True, msg='上传成功')
    except Exception as e:
        logger.error(f"Error uploading image: {str(e)}")
        return make_response(status='error', msg=str(e))
