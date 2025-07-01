from fastapi import APIRouter, Depends, HTTPException, Request, Query
import json
import os
import logging
import shutil
from pathlib import Path
from server.services.kg_service import KGService
from server.services.scene_service import SceneService
from server.utils.response import make_response
from server.config.config import load_config

router = APIRouter(prefix='/entity')
kg_service = KGService()
scene_service=SceneService()

@router.get('/character/list')
async def get_characters(project_name: str = Query(..., description="项目名称")):
    """获取项目中的所有角色信息"""
    try:
        if not project_name:
            return make_response(status='error', msg='项目不存在')
            
        # 获取实体列表
        characters = kg_service.inquire_entity_list(project_name)
        characters = json.loads(characters) if isinstance(characters, str) else characters
        
        # 获取锁定的实体列表
        locked_entities = kg_service.get_locked_entities(project_name)
        
        return make_response(data={
            'characters': characters,
            'locked_entities': locked_entities
        })
    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.post('/character/update')
async def update_character(request: Request):
    """更新角色信息"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        name = data.get('name')
        attributes = data.get('attributes', {})
        
        if not project_name:
            return make_response(status='error', msg='项目不存在')
            
        # 使用 kg_service 更新实体属性，并自动保存
        result = kg_service.modify_entity(project_name, name, attributes, save_kg=True)
        return make_response(data=result)
    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.post('/character/toggle_lock')
async def toggle_lock(request: Request):
    """锁定/解锁实体提示词"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        entity_name = data.get('entity_name')
        
        if not project_name:
            return make_response(status='error', msg='项目不存在')
            
        # 使用 kg_service 切换实体锁定状态，并自动保存
        is_locked = kg_service.toggle_entity_lock(project_name, entity_name, save_kg=True)
        return make_response(data={'is_locked': is_locked})
    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.delete('/character/{name}')
async def delete_character(name: str, project_name: str = Query(..., description="项目名称")):
    """
    删除角色实体
    
    参数:
        name (str): 实体名称
        
    返回:
        dict: 响应结果
    """
    try:
        if not project_name:
            return make_response(status='error', msg='项目不存在')
            
        # 删除实体，并自动保存
        result = kg_service.delete_entity(project_name, name, save_kg=True)
        
        # 删除对应的参考图文件夹
        try:
            config = load_config()
            projects_path = config.get('projects_path', 'projects')
            character_folder = Path(projects_path) / project_name / "Character" / name
            if character_folder.exists() and character_folder.is_dir():
                shutil.rmtree(character_folder)
                logging.info(f"成功删除角色文件夹: {character_folder}")
        except Exception as folder_e:
            # 即使文件夹删除失败，也只记录日志，不影响主流程
            logging.error(f"删除角色参考图文件夹 {name} 时失败: {folder_e}")
        
        # 检查删除结果
        if '成功' in result:
            return make_response(data=True)
        else:
            return make_response(status='error', msg=result)
            
    except Exception as e:
        logging.error(f"删除实体时出错: {str(e)}")
        return make_response(status='error', msg=str(e))

@router.get('/scene/list')
async def get_scenes(project_name: str = Query(..., description="项目名称")):
    """获取项目中的所有基底场景信息"""
    try:
        if not project_name:
            return make_response(status='error', msg='项目不存在')
            
        # 获取实体列表
        scenes = scene_service.load_scenes(project_name)
        scenes = json.loads(scenes) if isinstance(scenes, str) else scenes
        
        
        return make_response(data={
            'scenes': scenes,
        })
    except Exception as e:
        return make_response(status='error', msg=str(e))

@router.post('/scene/update')
async def update_scenes(request: Request):
    """更新角色信息"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        name = data.get('name')
        prompt = data.get('prompt', "")
   
        if not project_name:
            return make_response(status='error', msg='项目不存在')
        
        result = scene_service.update_scenes(project_name,{name:prompt},force_update=True)

        return make_response(data=result)
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.delete('/scene/{name}')
async def delete_scene(name: str, project_name: str = Query(..., description="项目名称")):
    """
    删除角色实体
    
    参数:
        name (str): 实体名称
        
    返回:
        dict: 响应结果
    """
    try:
        if not project_name:
            return make_response(status='error', msg='项目不存在')
            
       
        result = scene_service.delete_scenes(project_name, [name])
        
        # 删除对应的参考图文件夹
        try:
            config = load_config()
            projects_path = config.get('projects_path', 'projects')
            scene_folder = Path(projects_path) / project_name / "Scene" / name
            if scene_folder.exists() and scene_folder.is_dir():
                shutil.rmtree(scene_folder)
                logging.info(f"成功删除场景文件夹: {scene_folder}")
        except Exception as folder_e:
            # 即使文件夹删除失败，也只记录日志，不影响主流程
            logging.error(f"删除场景参考图文件夹 {name} 时失败: {folder_e}")

        # 检查删除结果
        if result:
            return make_response(data=result)
        else:
            return make_response(status='error', msg=result)
            
    except Exception as e:
        logging.error(f"删除实体时出错: {str(e)}")
        return make_response(status='error', msg=str(e))

@router.post('/character/create')
async def create_character(request: Request):
    """创建新角色实体"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        name = data.get('name')
        attributes = data.get('attributes', {})
        
        if not project_name:
            return make_response(status='error', msg='项目不存在')
            
        # 使用 kg_service 创建新实体，并自动保存
        result = kg_service.new_entity(project_name, name, attributes, save_kg=True)
        return make_response(data=result)
    except Exception as e:
        logging.error(f"创建实体时出错: {str(e)}")
        return make_response(status='error', msg=str(e))

@router.post('/scene/create')
async def create_scene(request: Request):
    """创建新场景"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        name = data.get('name')
        prompt = data.get('prompt', "")
        
        if not project_name:
            return make_response(status='error', msg='项目不存在')
        
        # 使用 scene_service 创建新场景，并自动保存
        scene_dict = {name: prompt}
        result = scene_service.update_scenes(project_name, scene_dict, force_update=True)
        return make_response(data=result)
    except Exception as e:
        logging.error(f"创建场景时出错: {str(e)}")
        return make_response(status='error', msg=str(e))
