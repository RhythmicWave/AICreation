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
from .workflow_service import WorkflowService
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
        
        # 依赖服务
        self.workflow_service = WorkflowService()
        
        # 任务管理
        if not hasattr(self, 'tasks'):
            self.tasks = {}
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
        
        ws_thread = threading.Thread(target=self._ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        start_time = time.time()
        while not self._ws_connected and not self._ws_error and time.time() - start_time < 10:
            time.sleep(0.1)
            
        if self._ws_error:
            raise Exception(f"Failed to connect to WebSocket: {self._ws_error}")
        if not self._ws_connected:
            raise Exception("WebSocket connection timeout")
            
        return self._ws
        
    def _send_workflow(self, workflow: Dict[str, Any]) -> str:
        """发送工作流到 ComfyUI。"""
        try:
            payload = {
                "prompt": workflow,
                "client_id": self.client_id
            }
            response = requests.post(f"{self.comfyui_url}/prompt", json=payload)
           
            if response.status_code != 200:
                raise Exception(f"{response.text}")
                
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
            for message in self._ws_messages[:]:
                if not isinstance(message, dict):
                    continue
                    
                if message['type'] == 'executing':
                    data = message.get('data', {})
                    if data.get('prompt_id') == prompt_id and data.get('node') is None:
                        time.sleep(1)
                        try:
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
        
    def generate_images(
        self,
        prompts: List[str],
        output_dirs: List[str] = None,
        workflow: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """批量生成图片。"""
        if not isinstance(prompts, list):
            prompts = [prompts]
            
        if output_dirs and len(output_dirs) != len(prompts):
            raise ValueError("output_dirs的长度必须与prompts相同")
            
        if not output_dirs:
            output_dirs = [None] * len(prompts)
            
        task_id = f"img_{time.strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting batch generation with workflow: {workflow}")
        
        workflow_data = self.workflow_service.load_workflow(workflow)
        workflow_error = None
        if not workflow_data:
            workflow_error = f'Workflow file not found or failed to load: {workflow}'

        self.tasks[task_id] = {
            'status': 'error' if workflow_error else 'running',
            'total': len(prompts),
            'current': 0,
            'errors': [workflow_error] if workflow_error else [],
            'current_prompt': None,
            'outputs': {}
        }
        
        if not workflow_error:
            def generate_worker():
                try:
                    for i, (prompt, output_dir) in enumerate(zip(prompts, output_dirs)):
                        if self.tasks[task_id].get('status') == 'cancelled':
                            break
                        
                        self.tasks[task_id]['current'] = i
                        self.tasks[task_id]['current_prompt'] = prompt
                        
                        current_params = params.copy() if params else {}
                        current_params['seed'] = self.generate_seed()
                        
                        # 使用克隆的工作流数据以避免修改原始数据
                        current_workflow = json.loads(json.dumps(workflow_data))
                        
                        current_workflow = self.workflow_service.update_workflow_prompt(current_workflow, prompt, current_params.get('negative_prompt', ''))
                        current_workflow = self.workflow_service.update_workflow_seed(current_workflow, current_params['seed'])
                        current_workflow = self.workflow_service.update_workflow_params(current_workflow, current_params)
                        if self.config['comfyui'].get('reference_image_mode', True) and current_params.get('reference_image_paths'):
                            ref_paths = current_params.get('reference_image_paths')
                            if i < len(ref_paths):
                                current_workflow = self.workflow_service.update_workflow_reference_image(current_workflow, ref_paths[i])
                        
                        self._connect_websocket()
                        
                        try:
                            prompt_id = self._send_workflow(current_workflow)
                            success, history = self._wait_for_execution(prompt_id)
                            
                            if not success:
                                self.tasks[task_id]['errors'].append(f"Failed to generate image for prompt: {prompt}")
                                continue
                                
                            if history and 'outputs' in history:
                                for node_id, node_output in history['outputs'].items():
                                    if 'images' in node_output and node_output['images']:
                                        image = node_output['images'][0]
                                        if output_dir:
                                            self._save_image(image, output_dir)
                                        self.tasks[task_id]['outputs'][node_id] = {'images': node_output['images']}
                                        
                            self.tasks[task_id]['current'] += 1
                            
                        except Exception as e:
                            self.tasks[task_id]['errors'].append(f"Error processing prompt '{prompt}': {str(e)}")
                        finally:
                            if self._ws:
                                self._ws.close()
                                self._ws = None
                                self._ws_messages = []
                                self._ws_connected = False
                                self._ws_error = None
                    
                    if not self.tasks[task_id]['errors']:
                        self.tasks[task_id]['status'] = 'completed'
                    else:
                        self.tasks[task_id]['status'] = 'error'

                except Exception as e:
                    self.tasks[task_id]['status'] = 'error'
                    self.tasks[task_id]['errors'].append(str(e))
                    logger.error(f"Error in generation worker for task {task_id}: {str(e)}")
                    
                finally:
                    self.tasks[task_id]['current_prompt'] = None
                    logger.info(f"Task {task_id} finished with status: {self.tasks[task_id]['status']}")
                    
            worker_thread = threading.Thread(target=generate_worker)
            worker_thread.daemon = True
            worker_thread.start()
        
        return {
            'task_id': task_id,
            'total': len(prompts),
            'status': self.tasks[task_id]['status'],
            'errors': self.tasks[task_id]['errors']
        }

    def _save_image(self, image_data: Dict[str, Any], output_dir: str):
        """保存生成的图片到指定目录。"""
        try:
            image_url = f"{self.comfyui_url}/view"
            image_params = {
                'filename': image_data['filename'],
                'subfolder': image_data.get('subfolder', ''),
                'type': image_data.get('type', 'output')
            }
            image_response = requests.get(image_url, params=image_params)
            if image_response.status_code == 200:
                output_path = os.path.join(output_dir, "image.png")
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(image_response.content)
                print(f"Saved generated image to {output_path}")
            else:
                raise Exception(f"Failed to download image: {image_response.status_code}")
        except Exception as e:
            self.tasks[task_id]['errors'].append(f"Failed to save image: {str(e)}")

    def get_generation_progress(self, task_id: str) -> Dict[str, Any]:
        """获取生成进度。"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'not_found'}
        return {
            'status': task['status'],
            'current': task['current'],
            'total': task['total'],
            'errors': task.get('errors', []),
            'current_prompt': task.get('current_prompt')
        }

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态。"""
        return self.tasks.get(task_id, {'status': 'not_found'})
        
    def cancel_generation(self, task_id: str) -> bool:
        """取消生成任务。"""
        if task_id not in self.tasks:
            return False
        
        self.tasks[task_id]['status'] = 'cancelling'
        try:
            response = requests.post(f"{self.comfyui_url}/interrupt")
            if response.status_code == 200:
                self.tasks[task_id]['status'] = 'cancelled'
                return True
            else:
                self.tasks[task_id]['status'] = 'running' # Restore status
                return False
        except Exception as e:
            self.tasks[task_id]['status'] = 'running' # Restore status
            return False

    def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有可用的工作流。"""
        return self.workflow_service.list_workflows()

    def get_workflow(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定工作流的详细信息。"""
        return self.workflow_service.get_workflow(name)
