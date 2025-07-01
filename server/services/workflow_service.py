import json
import os
from typing import Dict, List, Optional, Any
from .base_service import SingletonService

class WorkflowService(SingletonService):
    def _initialize(self):
        """初始化工作流服务。"""
        # 获取服务器根目录
        self.server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.workflow_dir = os.path.join(self.server_root, "workflow")

    def load_workflow(self, workflow_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """加载工作流配置。"""
        if workflow_name is None:
            workflow_name = "default_workflow.json"
            
        workflow_path = os.path.join(self.workflow_dir, workflow_name)
        
        print(f"Loading workflow from: {workflow_path}")
        
        try:
            if not os.path.exists(workflow_path):
                if os.path.exists(workflow_name):
                    workflow_path = workflow_name
                else:
                    print(f"Workflow file not found at: {workflow_path}")
                    if not workflow_name.endswith('.json'):
                        workflow_path = os.path.join(self.workflow_dir, workflow_name + '.json')
                        if not os.path.exists(workflow_path):
                            print(f"Workflow file not found at: {workflow_path}")
                            return None
                    else:
                        return None
                
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
                if not isinstance(workflow_data, dict):
                    print(f"Invalid workflow format in {workflow_name}")
                    return None
                return workflow_data
        except Exception as e:
            print(f"Error loading workflow: {str(e)}")
            return None
    
    def update_workflow_prompt(self, workflow: Dict[str, Any], prompt: str, negative_prompt: str = '') -> Dict[str, Any]:
        """更新工作流中的提示词。"""
        for node in workflow.values():
            if node.get('class_type') == 'CLIPTextEncodeFlux':
                title = str.lower(node['_meta'].get('title', ''))
                if 'negative' in title:
                    if negative_prompt:
                        node['inputs']['clip_l'] = negative_prompt
                        node['inputs']['t5xxl'] = negative_prompt
                else:
                    node['inputs']['clip_l'] = prompt
                    node['inputs']['t5xxl'] = prompt
            elif node.get('class_type') == 'CLIPTextEncode':
                title = str.lower(node['_meta'].get('title', ''))
                if 'negative' in title:
                    if negative_prompt:
                        node['inputs']['text'] = negative_prompt
                else:
                    node['inputs']['text'] = prompt
        return workflow

    def update_workflow_seed(self, workflow: Dict[str, Any], seed: int) -> Dict[str, Any]:
        """更新工作流中的随机种子。"""
        for node in workflow.values():
            if node.get('class_type') in ['RandomNoise', 'KSampler']:
                seed_key = 'noise_seed' if node.get('class_type') == 'RandomNoise' else 'seed'
                node['inputs'][seed_key] = seed
                break
        return workflow

    def update_workflow_params(self, workflow: Dict[str, Any], params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """更新工作流中的其他参数。"""
        if not params:
            return workflow
        for node in workflow.values():
            if node.get('class_type') == 'EmptyLatentImage':
                if 'width' in params:
                    node['inputs']['width'] = params['width']
                if 'height' in params:
                    node['inputs']['height'] = params['height']
        return workflow
    
    def update_workflow_reference_image(self, workflow: Dict[str, Any], reference_image_paths: List[str]) -> Dict[str, Any]:
        """更新工作流中的参考图片，并删除无效的依赖。"""
        delete_nodes = []
        table = {"one": 0, "two": 1, "three": 2}

        if reference_image_paths[1]=='' and reference_image_paths[2]!='':
            reference_image_paths=(reference_image_paths[0],reference_image_paths[2],'')

        for k, node in workflow.items():
            if node.get('class_type') == 'JDC_ImageLoader':
                title = str.lower(node['_meta'].get('title', ''))
                for key, value in table.items():
                    if key in title:
                        if value < len(reference_image_paths) and reference_image_paths[value]!='':
                            node['inputs']['image'] = reference_image_paths[value]
                        else:
                            delete_nodes.append(k)

        if delete_nodes:
            print(f"Nodes to delete due to missing reference images: {delete_nodes}")
            return self.delete_workflow_nodes(workflow, delete_nodes)
        return workflow

    def _get_required_inputs_for_node(self, node: Dict[str, Any]) -> List[str]:
        """获取节点的必需输入列表。"""
        class_type = node.get('class_type', '')
        required_inputs = {
            'KSampler': ['model', 'positive', 'negative', 'latent_image'],
            'VAEDecode': ['samples', 'vae'],
            'VAEEncode': ['pixels', 'vae'],
            'ImageStitch': ['image1'],
            'ReferenceLatent': ['conditioning', 'latent'],
            'FluxGuidance': ['conditioning'],
            'ConditioningZeroOut': ['conditioning'],
            'FluxKontextImageScale': ['image'],
            'PreviewImage': ['images']
        }
        return required_inputs.get(class_type, [])

    def delete_workflow_nodes(self, workflow: Dict[str, Any], nodes_to_delete: List[str]) -> Dict[str, Any]:
        """
        删除工作流中的节点，并智能地尝试重新连接依赖关系以保持工作流的完整性。
        """
        if not nodes_to_delete:
            return workflow

        all_nodes_to_delete = set(nodes_to_delete)
        
        graph_changed = True
        while graph_changed:
            graph_changed = False
            initial_delete_count = len(all_nodes_to_delete)

            for node_id in list(workflow.keys()):
                if node_id in all_nodes_to_delete:
                    continue

                node = workflow[node_id]
                inputs = node.get('inputs', {})
                should_delete_node = False

                for input_name, input_value in list(inputs.items()):
                    if isinstance(input_value, list) and input_value:
                        ref_node_id = str(input_value[0])
                        if ref_node_id in all_nodes_to_delete:
                            ref_node = workflow.get(ref_node_id)
                            can_rewire = False
                            if ref_node and input_name in ref_node.get('inputs', {}):
                                new_source_input = ref_node['inputs'][input_name]
                                if isinstance(new_source_input, list) and new_source_input and str(new_source_input[0]) != node_id:
                                    print(f"Re-wiring node {node_id}: input '{input_name}' from {ref_node_id} to {new_source_input[0]}")
                                    inputs[input_name] = new_source_input
                                    can_rewire = True
                                    graph_changed = True
                            
                            if not can_rewire:
                                if input_name in self._get_required_inputs_for_node(node):
                                    should_delete_node = True
                                    break
                                else:
                                    inputs.pop(input_name, None)
                                    graph_changed = True
                
                if should_delete_node:
                    all_nodes_to_delete.add(node_id)

            if len(all_nodes_to_delete) > initial_delete_count:
                graph_changed = True
        
        for node_id in all_nodes_to_delete:
            if node_id in workflow:
                del workflow[node_id]
        
        return workflow

    def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有可用的工作流。"""
        workflows = []
        try:
            for filename in os.listdir(self.workflow_dir):
                if filename.endswith('.json'):
                    workflow_path = os.path.join(self.workflow_dir, filename)
                    try:
                        with open(workflow_path, 'r', encoding='utf-8') as f:
                            workflow_data = json.load(f)
                            info = {
                                'name': filename,
                                'path': workflow_path,
                                'size': os.path.getsize(workflow_path),
                                'modified': os.path.getmtime(workflow_path)
                            }
                            # Extract more details if possible
                            workflows.append(info)
                    except Exception as e:
                        print(f"Error loading workflow info {filename}: {str(e)}")
            return sorted(workflows, key=lambda x: x['name'])
        except Exception as e:
            print(f"Error listing workflows: {str(e)}")
            return []

    def get_workflow(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定工作流的详细信息。"""
        if not name.endswith('.json'):
            name += '.json'
        
        workflow_path = os.path.join(self.workflow_dir, name)
        if not os.path.exists(workflow_path):
            return None
            
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
            
            metadata = {
                'name': name,
                'path': workflow_path,
                'size': os.path.getsize(workflow_path),
                'modified': os.path.getmtime(workflow_path),
                'nodes': {
                    node_id: {
                        'type': node.get('class_type'),
                        'title': node.get('_meta', {}).get('title'),
                        'inputs': node.get('inputs', {})
                    } for node_id, node in workflow.items() if isinstance(node, dict)
                }
            }
            return {'metadata': metadata, 'workflow': workflow}
        except Exception as e:
            print(f"Error getting workflow {name}: {str(e)}")
            return None 