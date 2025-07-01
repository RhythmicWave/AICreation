import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
import os
from server.config.config import load_config
import json
from datetime import datetime
from server.utils.response import make_response

from server.services.llm_service import LLMService
from server.services.chapter_file_service import ChapterFileService
import logging
from fastapi.responses import StreamingResponse

router = APIRouter(prefix='/chapter')
llm_service = LLMService()
chapter_file_server=ChapterFileService()

@router.post('/create')
async def create_chapter(request: Request):
    """创建新章节"""
    data = await request.json()
    project_name = data.get('project_name')

    if not project_name:
        return make_response(status='error', msg='缺少必要参数')

    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')
        project_path = os.path.join(projects_path, project_name)

        # 获取最新章节号
        latest_num = chapter_file_server.get_latest_chapter(project_path)
        new_chapter = f'chapter{latest_num + 1}'
        new_chapter_path = os.path.join(project_path, new_chapter)
        
        # 创建新章节目录和content.txt文件
        os.makedirs(new_chapter_path, exist_ok=True)
        content_file = os.path.join(new_chapter_path, 'content.txt')
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write('')

        return make_response(data={'chapter': new_chapter}, msg='创建成功')

    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.post('/generate')
async def generate_chapter(request: Request):
    """生成章节内容"""
    data = await request.json()
    project_name = data.get('project_name')
    chapter_name = data.get('chapter_name')
    prompt = data.get('prompt')
    is_continuation = data.get('is_continuation', False)
    use_last_chapter = data.get('use_last_chapter', True)

    if not all([project_name, chapter_name, prompt]):
        return make_response(status='error', msg='缺少必要参数')

    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')
        chapter_path = os.path.join(projects_path, project_name, chapter_name)

        if not os.path.exists(chapter_path):
            return make_response(status='error', msg='章节路径不存在')

        # 获取上一章内容作为上下文
        if use_last_chapter:
            last_content = chapter_file_server.get_chapter_content(project_name, f'chapter{int(chapter_name[7:]) - 1}')
        else:
            last_content = ''
        
        # 创建一个生成器
        async def event_stream():
            try:
                if is_continuation:
                    generator =llm_service.continue_story(prompt, project_name, last_content)
                else:
                    generator =llm_service.generate_text(prompt, project_name, last_content)

                async for generated_text in generator:
                    if await request.is_disconnected():
                        break
                    yield f"data: {generated_text}\n\n"
            except asyncio.CancelledError:
                # 处理客户端断开连接
                print("客户端中断了连接")
            finally:
                # 执行必要的清理操作
                if 'generator' in locals():
                    await generator.aclose()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.post('/save')
async def save_chapter_content(request: Request):
    """保存章节内容"""
    data = await request.json()
    project_name = data.get('project_name')
    chapter_name = data.get('chapter_name')
    content = data.get('content')

    if not all([project_name, chapter_name, content]):
        return make_response(status='error', msg='缺少必要参数')

    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')
        chapter_path = os.path.join(projects_path, project_name, chapter_name)

        if not os.path.exists(chapter_path):
            os.makedirs(chapter_path)

        # 保存内容
        content_file = os.path.join(chapter_path, 'content.txt')
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return make_response(msg='保存成功')

    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.post('/split_text')
async def split_text(request: Request):
    data = await request.json()
    project_name = data.get('project_name')
    chapter_name = data.get('chapter_name')
    
    if not project_name or not chapter_name:
        return make_response(status='error', msg='Missing project_name or chapter_name')
    
    try:
        # 使用 llm_service 获取章节内容
        content = chapter_file_server.get_chapter_content(project_name, chapter_name)
        if not content:
            return make_response(status='error', msg=f'Content not found for chapter {chapter_name}')
        
        # 调用 llm_service 进行文本分割和描述词生成
        spans_and_prompts =await llm_service.split_text_and_generate_prompts(project_name, content)
        
        # 检查是否有错误
        if not spans_and_prompts:
             return make_response(status='error', msg='文本分割失败，请重试。')

        if all('error' in span for span in spans_and_prompts):
            return make_response(status='error', msg='文本分割失败', detail=spans_and_prompts)

        print("切割数量",len(spans_and_prompts))
        print("spans_and_prompts",spans_and_prompts)
        # 生成对应的文件
        chapter_file_server.generate_span_files(project_name, chapter_name, spans_and_prompts)
            
        return make_response(status='success', msg='分割成功', data=spans_and_prompts)
        
    except Exception as e:
        return make_response(status='error', msg=f'分割文本时发生错误：{str(e)}')

@router.get('/list')
async def get_chapter_list(project_name: str):
    """获取项目的所有章节列表"""
    if not project_name:
        return make_response(status='error', msg='项目名称不能为空')

    config = load_config()
    projects_path = config.get('projects_path', 'projects/')
    project_path = os.path.join(projects_path, project_name)

    if not os.path.exists(project_path):
        return make_response(status='error', msg='项目不存在')

    try:
        # 获取所有章节目录并排序
        chapters = []
        for item in sorted(os.listdir(project_path)):
            item_path = os.path.join(project_path, item)
            if os.path.isdir(item_path) and item.startswith('chapter'):
                chapters.append(item)
        
        return make_response(data=chapters)
    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.get('/content')
async def get_chapter_content(project_name: str, chapter_name: str):
    """获取指定章节的content.txt内容"""
    try:
        content = chapter_file_server.get_chapter_content(project_name, chapter_name)
        # 即使内容为空也返回成功，因为这是新建章节的正常情况
        return make_response(data={'content': content}, msg='获取成功')
        
    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.post('/extract_characters')
async def extract_characters(request: Request):
    """提取章节中的角色信息"""
    data = await request.json()
    project_name = data.get('project_name')
    chapter_name = data.get('chapter_name')

    if not all([project_name, chapter_name]):
        return make_response(status='error', msg='缺少必要参数')

    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')
        chapter_path = os.path.join(projects_path, project_name, chapter_name)
        content_file = os.path.join(chapter_path, 'content.txt')

        if not os.path.exists(content_file):
            return make_response(status='error', msg='章节内容文件不存在')

        # 读取章节内容
        with open(content_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 调用LLM服务提取角色
        characters =await llm_service.extract_character(content, project_name)
        return make_response(data=characters, msg='提取成功')

    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.get('/scene_list')
async def get_chapter_scene_list(project_name: str, chapter_name: str):
    """获取章节的场景列表"""
    if not project_name or not chapter_name:
        return make_response(status='error', msg='Missing project_name or chapter_name')
    
    try:
        config= load_config()
        projects_path = config.get('projects_path', 'projects/')
        chapter_dir = os.path.join(projects_path, project_name, chapter_name)
        if not os.path.exists(chapter_dir):
            return make_response(status='error', msg=f'Chapter directory not found: {chapter_dir}')
        
        scene_list = []
        # 遍历所有数字命名的子文件夹
        for item in sorted(os.listdir(chapter_dir), key=lambda x: int(x) if x.isdigit() else float('inf')):
            if not item.isdigit():
                continue
                
            span_dir = os.path.join(chapter_dir, item)
            if not os.path.isdir(span_dir):
                continue
                
            # 读取span.txt
            span_file = os.path.join(span_dir, 'span.txt')
            prompt_file = os.path.join(span_dir, 'prompt.json')
            
            if not os.path.exists(span_file) or not os.path.exists(prompt_file):
                continue
                
            with open(span_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_data = json.load(f)
                
            scene_list.append({
                'id': str(item),
                'content': content,
                'base_scene': prompt_data.get('base_scene', ''),
                'scene': prompt_data.get('scene', ''),
                'prompt': prompt_data.get('prompt', '')
            })
            
        return make_response(status='success', data=scene_list)
        
    except Exception as e:
        return make_response(status='error', msg=f'获取场景列表失败：{str(e)}')

@router.post('/translate_prompt')
async def translate_prompt(request: Request):
    """
    将场景描述转换为 AI 绘图提示词
    请求参数：
        project_name: 项目名称
        prompts: 场景描述列表
    返回：
        提示词列表
    """
    try:
        data = await request.json()
        project_name = data.get('project_name')
        prompts = data.get('prompts', [])
        
        if not project_name or not prompts:
            return make_response(status='error', msg='缺少必要参数')
            
        if not isinstance(prompts, list):
            return make_response(status='error', msg='prompts 必须是一个列表')


        translated_prompts =await llm_service.translate_prompt(project_name, prompts)
        return make_response(data=translated_prompts, msg='翻译提示词成功')
        
    except Exception as e:
        logging.error(f'转换提示词失败: {str(e)}')
        return make_response(status='error', msg=f'转换提示词失败：{str(e)}')

@router.post('/save_scenes')
async def save_scenes(request: Request):
    """
    保存场景修改
    """
    try:
        data = await request.json()
        project_name = data.get('project_name')
        chapter_name = data.get('chapter_name')
        scenes = data.get('scenes')
        
        if not all([project_name, chapter_name, scenes]):
            return make_response(status='error', msg='缺少必要参数')
            
        # 获取章节目录
        config = load_config()
        chapter_dir = os.path.join(config['projects_path'], project_name, chapter_name)
        if not os.path.exists(chapter_dir):
            return make_response(status='error', msg='章节不存在')
            
        # 保存每个场景的修改
        for scene in scenes:
            # 使用场景的序号
            scene_index = scene.get('id')
            if not scene_index:
                continue
                
            scene_dir = os.path.join(chapter_dir, str(scene_index))
            
            # 创建场景目录（如果不存在）
            os.makedirs(scene_dir, exist_ok=True)
            
            # 保存分割片段
            if 'span' in scene:
                with open(os.path.join(scene_dir, 'span.txt'), 'w', encoding='utf-8') as f:
                    f.write(scene['span'])
            
            # 保存场景描述和提示词
            if 'scene' in scene or 'prompt' in scene:
                prompt_data = {
                    'base_scene': scene.get('base_scene', ''),
                    'scene': scene.get('scene', ''),
                    'prompt': scene.get('prompt', '')
                }
                with open(os.path.join(scene_dir, 'prompt.json'), 'w', encoding='utf-8') as f:
                    json.dump(prompt_data, f, ensure_ascii=False, indent=2)
        
        return make_response(status='success', msg='保存成功')
        
    except Exception as e:
        logging.error(f'保存场景失败: {str(e)}')
        return make_response(status='error', msg=f'保存失败: {str(e)}')
