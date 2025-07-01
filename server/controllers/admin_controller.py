from fastapi import APIRouter, Depends, HTTPException, Request
from server.config.config import load_config, update_config,load_prompt_styler,save_prompt_styler
import os
import json
from server.utils.response import make_response

router = APIRouter(prefix='/admin')
config = load_config()

@router.get('/config')
async def get_config():
    """获取当前配置"""
    try:
        config = load_config()

        return make_response(
            data=config,
            msg='获取配置成功'
        )
    except Exception as e:
        return make_response(status='error', msg=f'获取配置时发生错误：{str(e)}')

@router.post('/config')
async def update_configuration(request: Request):
    """更新配置"""
    try:
        data = await request.json()
    except Exception:
        return make_response(status='error', msg='无效的 JSON 数据')
        
    if not data:
        return make_response(status='error', msg='配置数据不能为空')
        
    try:
        update_config(data)
        return make_response(
            data=data,
            msg='配置更新成功'
        )
    except Exception as e:
        return make_response(status='error', msg=f'更新配置时发生错误：{str(e)}')

@router.get('/prompt_styles')
async def get_prompt_styles():
    """获取所有提示词样式。"""
    try:

        styles=load_prompt_styler()
        
        return make_response(
            data={'styles': styles},
            msg='获取提示词样式成功'
        )
    except Exception as e:
        return make_response(status='error', msg=f'获取提示词样式时发生错误：{str(e)}')

@router.post('/prompt_styles')
async def save_prompt_styles(request: Request):
    """保存提示词样式。"""
    try:
        data = await request.json()
        styles = data.get('styles')
        
        if not styles:
            return make_response(status='error', msg='缺少样式数据')
            
        # 保存到prompt_styler.json文件
        save_prompt_styler(styles)
            
        return make_response(data=True,msg='保存提示词样式成功')
    except Exception as e:
        return make_response(status='error', msg=f'保存提示词样式时发生错误：{str(e)}')
