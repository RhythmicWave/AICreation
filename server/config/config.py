import json
import os
import yaml
from typing import Dict, Any

config = {}  # 所有模块共享的全局字典对象

def load_config() -> Dict[str, Any]:
    global config
    """从 config.yaml 加载配置并更新全局字典"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        new_config = yaml.safe_load(f) or {}
    
    # 清空并更新全局字典
    config.clear()
    config.update(new_config)
    
    # 处理计算属性
    server_dir = os.path.dirname(os.path.dirname(__file__))
    
    # 处理路径转换
    if 'relative_projects_path' in config and 'projects_path' not in config:
        config['projects_path'] = os.path.abspath(os.path.join(server_dir, config['relative_projects_path']))
    
    if 'relative_prompts_path' in config and 'prompts_path' not in config:
        config['prompts_path'] = os.path.abspath(os.path.join(server_dir, config['relative_prompts_path']))
    
    if 'default_workflow' in config and 'file' in config['default_workflow']:
        config['default_workflow']['file'] = os.path.abspath(os.path.join(server_dir, config['default_workflow']['file']))
    
    if 'relative_workflow_path' in config and 'workflow_path' not in config:
        config['workflow_path'] = os.path.abspath(os.path.join(server_dir, config['relative_workflow_path']))
    
    # 扫描工作流文件
    workflow_path = config.get('workflow_path', '')
    config['all_workflow'] = []
    if os.path.exists(workflow_path) and os.path.isdir(workflow_path):
        config['all_workflow'] = [f for f in os.listdir(workflow_path) if f.endswith('.json')]
    
    return config

def save_config(_config: Dict[str, Any]) -> None:
    global config
    """保存配置并更新全局字典（不包含计算属性）"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(_config, f, allow_unicode=True, sort_keys=False)
    
    # 仅更新基础配置项，保留内存中的计算属性
    config.clear()
    config.update(_config)
    # 注意：此处需要重新生成计算属性，故立即调用load_config()
    load_config()

def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    global config
    """更新配置并保持全局字典引用不变"""
    
    # 创建基础配置副本（过滤计算属性）
    filtered_config = {
        k: v for k, v in config.items()
        if k not in ['projects_path', 'prompts_path', 'workflow_path', 'all_workflow']
    }
    
    # 处理嵌套更新
    for key, value in updates.items():
        keys = key.split('.') if '.' in key else [key]
        current = filtered_config
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = value
    
    # 保存并重新加载配置
    save_config(filtered_config)
    return config

def load_prompt_styler():
    prompt_styler_path=os.path.join(os.path.dirname(__file__), 'prompt_styler.json')
    with open(prompt_styler_path, 'r', encoding='utf-8') as f:
        styles = json.load(f)
    return styles

def save_prompt_styler(styles):
    prompt_styler_path=os.path.join(os.path.dirname(__file__), 'prompt_styler.json')
    with open(prompt_styler_path, 'w', encoding='utf-8') as f:
        json.dump(styles, f, ensure_ascii=False, indent=4)

def get_prompt_style_by_name(style_name: str) -> Dict[str, Any] | None:
    """根据名称查找提示词样式"""
    styles = load_prompt_styler()
    for style in styles:
        if style.get('name') == style_name:
            return style
    return None