import json
import os
import time
import uuid
import random
import requests
import websocket
import threading
from typing import Dict, List, Optional, Tuple, Any
from .base_service import SingletonService
from queue import Queue
import logging

logger = logging.getLogger(__name__)

class ImageService(SingletonService):        
    def _initialize(self):
        """初始化图像服务。"""

        # 基本配置
        self.comfyui_url = self.config['comfyui']['api_url']
        self.ws_url = self.comfyui_url.replace('http', 'ws')
        self.client_id = str(uuid.uuid4())

        
        # 任务管理
        if not hasattr(self, 'tasks'):
            self.tasks = {}  # 用于存储任务状态
        if not hasattr(self, 'stop_flag'):
            self.stop_flag = False

        
        # WebSocket相关
        self._ws = None
        self._ws_connected = False
        self._ws_error = None
        self._ws_messages = []
        self._ws_queue = Queue()
        self._ws_lock = threading.Lock()
       
    def generate_seed(self) -> int:
        """生成随机种子。"""
        return random.randint(1, 1000000000)
        
    def _connect_websocket(self) -> websocket.WebSocketApp:
        """连接到 ComfyUI WebSocket。"""
        ws_url = f"{self.ws_url}/ws?clientId={self.client_id}"
   
        def on_message(ws, message):
            try:
                data = json.loads(message)
                self._ws_messages.append(data)
            except Exception as e:
                print(f"Error processing WebSocket message: {str(e)}")
                
        def on_error(ws, error):
            print(f"WebSocket error: {error}")
            self._ws_error = error
            
        def on_close(ws, close_status_code, close_msg):
            self._ws_connected = False
            
        def on_open(ws):
            self._ws_connected = True
            
        self._ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # 在新线程中启动 WebSocket
        ws_thread = threading.Thread(target=self._ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # 等待连接建立或出错
        start_time = time.time()
        while not self._ws_connected and not self._ws_error and time.time() - start_time < 10:
            time.sleep(0.1)
            
        if self._ws_error:
            raise Exception(f"Failed to connect to WebSocket: {self._ws_error}")
        if not self._ws_connected:
            raise Exception("WebSocket connection timeout")
            
        return self._ws
        
    def _load_workflow(self, workflow_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """加载工作流配置。"""
        if workflow_name is None:
            workflow_name = "default_workflow.json"
            
        # 获取服务器根目录
        server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        workflow_path = os.path.join(server_root, "workflow", workflow_name)
        
        print(f"Loading workflow from: {workflow_path}")  # 添加调试信息
        
        try:
            if not os.path.exists(workflow_path):
                # 尝试直接使用workflow_name（可能是完整路径）
                if os.path.exists(workflow_name):
                    workflow_path = workflow_name
                else:
                    print(f"Workflow file not found at: {workflow_path}")
                    if not workflow_name.endswith('.json'):
                        # 尝试添加.json后缀
                        workflow_path = os.path.join(server_root, "workflow", workflow_name + '.json')
                        if not os.path.exists(workflow_path):
                            print(f"Workflow file not found at: {workflow_path}")
                            return None
                    else:
                        return None
                
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
                # 确保工作流数据格式正确
                if not isinstance(workflow_data, dict):
                    print(f"Invalid workflow format in {workflow_name}")
                    return None
                return workflow_data
        except Exception as e:
            print(f"Error loading workflow: {str(e)}")
            return None
        
    def _update_workflow_prompt(self, workflow: Dict[str, Any], prompt: str,style='anime') -> Dict[str, Any]:
        """更新工作流中的提示词。"""
        for node_id, node in workflow.items():
            if node.get('class_type') == 'CLIPTextEncodeFlux':
                origin_prompt=node['inputs']['t5xxl'] 
                if 'bad' in origin_prompt or 'worst' in origin_prompt:#说明是负面提示词，不用更改
                    continue
                enhanced_prompt = f"{prompt}, {style}, masterpiece, best quality, 8K, HDR, highres"
                node['inputs']['clip_l'] = enhanced_prompt
                node['inputs']['t5xxl'] = enhanced_prompt
               
                break
            if node.get('class_type') == 'CLIPTextEncode':
                origin_prompt=node['inputs']['text']
                if 'bad' in origin_prompt or 'worst' in origin_prompt:#说明是负面提示词，不用更改
                    continue
                enhanced_prompt = f"({style}:1.2),{prompt},  masterpiece, best quality, 8K, HDR, highres"
                node['inputs']['text'] = enhanced_prompt
        return workflow
        
    def _update_workflow_seed(self, workflow: Dict[str, Any], seed: int) -> Dict[str, Any]:
        """更新工作流中的随机种子。"""
        for node_id, node in workflow.items():
            if node.get('class_type') == 'RandomNoise':
                node['inputs']['noise_seed'] = seed
                break
            if node.get('class_type') == 'KSampler':
                node['inputs']['seed'] = seed
                break
        return workflow
        
    def _update_workflow_params(self, workflow: Dict[str, Any], params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """更新工作流中的其他参数。"""
        if not params:
            return workflow
            
        for node in workflow.values():
                    
            if node.get('class_type') == 'EmptyLatentImage':
                inputs = node.get('inputs', {})
                if 'width' in params:
                    inputs['width'] = params['width']
                if 'height' in params:
                    inputs['height'] = params['height']
                    
        return workflow
        
    def _send_workflow(self, workflow: Dict[str, Any]) -> str:
        """发送工作流到 ComfyUI。"""
        try:
            payload = {
                "prompt": workflow,
                "client_id": self.client_id
            }
            response = requests.post(
                f"{self.comfyui_url}/prompt",
                json=payload
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to send workflow: {response.status_code}")
                
            result = response.json()
            prompt_id = result.get('prompt_id')
            if not prompt_id:
                raise Exception("No prompt_id in response")
                
            return prompt_id
            
        except Exception as e:
            raise Exception(f"Error sending workflow: {str(e)}")
            
    def _wait_for_execution(self, prompt_id: str, timeout: int = 60) -> Tuple[bool, Optional[Dict]]:
        """等待图片生成完成。"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            # 检查消息队列
            for message in self._ws_messages[:]:
                if not isinstance(message, dict):
                    continue
                    
                if message['type'] == 'executing':
                    data = message.get('data', {})
                    if data.get('prompt_id') == prompt_id:
                        if data.get('node') is None:  # 执行完成
                            # 等待一秒确保图片已保存
                            time.sleep(1)
                            try:
                                # 获取历史记录
                                response = requests.get(f"{self.comfyui_url}/history/{prompt_id}")
                                if response.status_code == 200:
                                    history = response.json()
                                    if history and prompt_id in history:
                                        return True, history[prompt_id]
                            except Exception as e:
                                print(f"获取历史记录失败: {str(e)}")
                            return False, None
                            
            time.sleep(0.1)
            
        print(f"等待执行超时: {prompt_id}")
        return False, None
        
    def _check_history_for_image(self, prompt_id: str) -> Tuple[bool, Optional[str]]:
        """从历史记录中检查图片。"""
        try:
            response = requests.get(f"{self.comfyui_url}/history/{prompt_id}")
            if response.status_code != 200:
                return False, None
                
            history = response.json()
            if not history or prompt_id not in history:
                return False, None
                
            outputs = history[prompt_id].get('outputs', {})
            for node_id, node_output in outputs.items():
                if 'images' in node_output and node_output['images']:
                    image = node_output['images'][0]
                    return True, image.get('filename')
                    
            return False, None
            
        except Exception as e:
            return False, None
            
            
    def generate_images(
        self,
        prompts: List[str],
        output_dirs: List[str] = None,
        workflow: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """批量生成图片。
        
        Args:
            prompts: 提示词列表
            output_dirs: 输出目录列表，长度必须与prompts相同
            workflow: 工作流文件名
            params: 生成参数
        """
        if not isinstance(prompts, list):
            prompts = [prompts]
            
        if output_dirs and len(output_dirs) != len(prompts):
            raise ValueError("output_dirs的长度必须与prompts相同")
            
        if not output_dirs:
            output_dirs = [None] * len(prompts)
            
        # 生成任务ID
        task_id = f"img_{time.strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting batch generation with workflow: {workflow}")
        logger.info(f"Starting batch worker for task {task_id}")
        
        # 检查工作流是否存在
        workflow_error = None
        if workflow:
            server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            workflow_path = os.path.join(server_root, "workflow", workflow)
            if not os.path.exists(workflow_path):
                workflow_error = f'Workflow file not found: {workflow}'
 
        
        # 确保 tasks 字典存在
        if not hasattr(self, 'tasks'):
            self.tasks = {}
            
        self.tasks[task_id] = {
            'status': 'error' if workflow_error else 'running',
            'total': len(prompts),
            'current': 0,
            'errors': [],
            'current_prompt': None,
            'error': workflow_error,
            'outputs': {}  # 存储每个节点的输出
        }
        
        if not workflow_error:
            def generate_worker():
                try:
                    for i, (prompt, output_dir) in enumerate(zip(prompts, output_dirs)):
                        if self.tasks[task_id]['status'] == 'cancelled':
                            print(f"Task {task_id} was cancelled")
                            break
                        self.tasks[task_id]['current'] = i
                        self.tasks[task_id]['current_prompt'] = prompt
                        
                        # 为每个图片生成新的随机种子
                        current_params = params.copy() if params else {}
                        current_params['seed'] = self.generate_seed()
                        
                        # 加载工作流
                        workflow_data = self._load_workflow(workflow)
                        if not workflow_data:
                            self.tasks[task_id]['errors'].append(f"Failed to load workflow for prompt: {prompt}")
                            continue
                            
                        # 更新工作流参数
                        workflow_data = self._update_workflow_prompt(workflow_data, prompt,current_params['style'])
                        workflow_data = self._update_workflow_seed(workflow_data, current_params['seed'])
                        workflow_data = self._update_workflow_params(workflow_data, current_params)
                        
                        # 连接 WebSocket
                        self._connect_websocket()
                        
                        try:
                            # 发送工作流到 ComfyUI
                            prompt_id = self._send_workflow(workflow_data)
                            
                            # 等待执行完成并获取输出
                            success, history = self._wait_for_execution(prompt_id)
                            if not success:
                                self.tasks[task_id]['errors'].append(f"Failed to generate image for prompt: {prompt}")
                                continue
                                
                            # 处理输出
                            if history and 'outputs' in history:
                                for node_id, node_output in history['outputs'].items():
                                    if 'images' in node_output and node_output['images']:
                                        image = node_output['images'][0]
                                        
                                        # 如果指定了输出目录，保存图片
                                        if output_dir:
                                            try:
                                                # 下载图片
                                                image_url = f"{self.comfyui_url}/view"
                                                image_params = {
                                                    'filename': image['filename'],
                                                    'subfolder': image.get('subfolder', ''),
                                                    'type': image.get('type', 'output')
                                                }
                                                image_response = requests.get(image_url, params=image_params)
                                                if image_response.status_code == 200:
                                                    # 保存图片
                                                    output_path = os.path.join(output_dir, "image.png")
                                                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                                    with open(output_path, 'wb') as f:
                                                        f.write(image_response.content)
                                                    print(f"Saved generated image to {output_path}")
                                                else:
                                                    raise Exception(f"Failed to download image: {image_response.status_code}")
                                            except Exception as e:
                                                self.tasks[task_id]['errors'].append(f"Failed to save image: {str(e)}")
                                                continue
                                        
                                        # 存储输出信息
                                        self.tasks[task_id]['outputs'][node_id] = {
                                            'images': node_output['images']
                                        }
                                        
                            self.tasks[task_id]['current'] += 1
                            
                        except Exception as e:
                            self.tasks[task_id]['errors'].append(f"Error processing prompt: {str(e)}")
                        finally:
                            if self._ws:
                                self._ws.close()
                                self._ws = None
                                self._ws_messages = []
                                self._ws_connected = False
                                self._ws_error = None
                                
                    if self.tasks[task_id]['status'] != 'cancelled':
                        self.tasks[task_id]['status'] = 'completed'
                        
                except Exception as e:
                    self.tasks[task_id]['status'] = 'error'
                    self.tasks[task_id]['errors'].append(str(e))
                    
                finally:
                    self.tasks[task_id]['current_prompt'] = None
                    print(f"Task {task_id} completed with status: {self.tasks[task_id]['status']}")
                    
            # 在新线程中启动生成任务
            worker_thread = threading.Thread(target=generate_worker)
            worker_thread.daemon = True
            worker_thread.start()
        
        return {
            'task_id': task_id,
            'total': len(prompts),
            'status': self.tasks[task_id]['status'],
            'errors': self.tasks[task_id]['errors']
        }
        
    def get_generation_progress(self, task_id: str) -> Dict[str, Any]:
        """获取生成进度。"""
        if task_id not in self.tasks:
            return {
                'status': 'not_found',
                'completed': 0,
                'total': 0,
                'current_prompt': None
            }
            
        task = self.tasks[task_id]
        return {
            'status': task['status'],
            'current': task['current'],
            'total': task['total'],
            'errors': task.get('errors', []),
            'current_prompt': task.get('current_prompt')
        }
        

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态。"""
        if task_id not in self.tasks:
            return {'status': 'not_found'}
        return self.tasks[task_id]
        
    def cancel_generation(self, task_id: str) -> bool:
        """取消生成任务。"""
        if task_id not in self.tasks:
            return False
            
        try:
            # 先设置任务状态为取消中
            self.tasks[task_id]['status'] = 'cancelling'
            
            # 调用 ComfyUI 的中断接口
            response = requests.post(f"{self.comfyui_url}/interrupt")
            if response.status_code == 200:
                # 更新任务状态为已取消
                self.tasks[task_id]['status'] = 'cancelled'
                return True
            else:
                print(f"取消任务失败: {response.status_code}")
                # 如果取消失败，恢复任务状态
                self.tasks[task_id]['status'] = 'running'
        except Exception as e:
            print(f"取消任务失败: {str(e)}")
            # 如果发生异常，恢复任务状态
            self.tasks[task_id]['status'] = 'running'
        return False
        
    def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有可用的工作流。"""
        workflow_dir = "workflow"
        workflows = []
        
        try:
            for filename in os.listdir(workflow_dir):
                if filename.endswith('.json'):
                    workflow_path = os.path.join(workflow_dir, filename)
                    try:
                        with open(workflow_path, 'r', encoding='utf-8') as f:
                            workflow = json.load(f)
                            # 提取工作流的基本信息
                            info = {
                                'name': filename,
                                'path': workflow_path,
                                'size': os.path.getsize(workflow_path),
                                'modified': os.path.getmtime(workflow_path)
                            }
                            # 尝试提取更多信息
                            for node in workflow.values():
                                if isinstance(node, dict):
                                    meta = node.get('_meta', {})
                                    if meta.get('title') == 'KSampler':
                                        info['sampler'] = node.get('inputs', {}).get('sampler_name')
                                    elif meta.get('title') == 'EmptyLatentImage':
                                        inputs = node.get('inputs', {})
                                        info['width'] = inputs.get('width')
                                        info['height'] = inputs.get('height')
                            workflows.append(info)
                    except Exception as e:
                        print(f"Error loading workflow {filename}: {str(e)}")
                        
            return sorted(workflows, key=lambda x: x['name'])
            
        except Exception as e:
            print(f"错误: {str(e)}")
            return []
            
    def get_workflow(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定工作流的详细信息。"""
        if not name.endswith('.json'):
            name += '.json'
            
        workflow_path = os.path.join("workflow", name)
        
        try:
            if not os.path.exists(workflow_path):
                return None
                
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
                
            # 添加工作流的元数据
            metadata = {
                'name': name,
                'path': workflow_path,
                'size': os.path.getsize(workflow_path),
                'modified': os.path.getmtime(workflow_path),
                'nodes': {}
            }
            
            # 分析工作流中的节点
            for node_id, node in workflow.items():
                if isinstance(node, dict):
                    node_info = {
                        'type': node.get('class_type'),
                        'title': node.get('_meta', {}).get('title'),
                        'inputs': node.get('inputs', {})
                    }
                    metadata['nodes'][node_id] = node_info
                    
            return {
                'metadata': metadata,
                'workflow': workflow
            }
            
        except Exception as e:
            print(f"错误 {name}: {str(e)}")
            return None
