import os
import json
import logging
import re
import asyncio
from typing import AsyncGenerator, List, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler


from server.services.base_service import SingletonService
from server.services.kg_service import KGService
from server.services.scene_service import SceneService

logger = logging.getLogger(__name__)

class LLMService(SingletonService):
    """使用LangChain重构的LLM服务类"""
    
    _prompt_cache: Dict[str, str] = {}

    def _initialize(self):
        self.api_key = self.config['llm']['api_key']
        self.api_url = self.config['llm']['api_url']
        self.model_name = self.config['llm']['model_name']

        self.prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts')
        self.projects_path = self.config.get('projects_path', 'projects/')
        self.kg_service = KGService()
        self.scene_service = SceneService()

        
        # 初始化LangChain LLM
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.api_url,
            model=self.model_name,
            temperature=0.5,
            timeout=120,
            max_retries=5,
            streaming=True,
        )
        
        
        self.agent=initialize_agent(
            tools=[],
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,

        )


    def _load_prompt(self, prompt_file: str) -> str:
        """加载提示词模板"""
        if prompt_file in self._prompt_cache:
            return self._prompt_cache[prompt_file]
            
        prompt_path = os.path.join(self.prompts_dir, prompt_file)
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f'提示词模板不存在：{prompt_file}')
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt = f.read()
            
        self._prompt_cache[prompt_file] = prompt
        return prompt

    def _create_agent_executor(self,tools: List[Tool] = None):
        """创建Agent执行器"""
        if tools is None or len(tools) == 0:
            return self.agent
        
        agent=initialize_agent(
            tools=tools,
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=False,#是否打印详细日志
            handle_parsing_errors=True,

        )
        
        
        return agent

    async def _process_text_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """处理文本流"""
        callback = AsyncIteratorCallbackHandler()
        # 使用 asyncio.create_task 来运行 LLM 调用，以便 callback.aiter() 可以立即开始迭代
        task = asyncio.create_task(
            self.llm.ainvoke(messages, config={"callbacks": [callback]})
        )
        async for token in callback.aiter():
            yield token
        # 确保LLM调用任务完成
        await task

    async def split_text_and_generate_prompts(self, project_name: str, text: str) -> List[dict]:
        """分割文本并生成描述词"""
        window_size = self.config['llm'].get('window_size', -1)
        
        # 预处理文本
        split_pattern = r'(?<=[。！？])(?![^""]*"")\s*'
        sentences = [s.replace('\n', ' ').strip() for s in re.split(split_pattern, text) if s.strip()]
        text = "\n".join(sentences)

        # 场景提取
        scene_generation_prompt_template = self._load_prompt("scene_extraction.txt")
        scene_names = self.scene_service.get_scene_names(project_name)
        system_prompt_for_scene = scene_generation_prompt_template.replace("{scenes}", ",".join(scene_names))
        
        # 创建LangChain Agent
        agent_executor_scene = self._create_agent_executor()
        #组合提示词并调用，其中system_prompt_for_scene是系统提示词，text是用户输入的文本，project_name是项目名称
        response_scene = await agent_executor_scene.ainvoke(self.combine_prompts(system_prompt_for_scene, text, project_name))
        response=response_scene['output']
        self.scene_service.update_scenes(project_name, response)

        # 文本描述生成
        text_desc_prompt_template = self._load_prompt("text_desc_prompt.txt")
        
        entities_names=self.kg_service.inquire_entity_names(project_name)
        scene_names = self.scene_service.get_scene_names(project_name)
        
        current_text_desc_prompt = text_desc_prompt_template.replace("{scenes}", ",".join(scene_names))
        current_text_desc_prompt = current_text_desc_prompt.replace("{entities}", ",".join(entities_names))

        # 处理文本块
        text_chunks = [text] if window_size <= 0 else [
            "\n".join(sentences[i:i+window_size]) 
            for i in range(0, len(sentences), window_size)
        ]

        async def process_chunk(chunk):
            response = await agent_executor_scene.ainvoke(self.combine_prompts(current_text_desc_prompt, chunk))
            try:
                output = response.get('output')

                if not output:
                    logger.warning(f"LLM response for text description is empty.")
                    return []
                
                # Langchain agents can return the result in different formats.
                # Sometimes it's a dict, sometimes a JSON string.
                if isinstance(output, str):
                    try:
                        # It may also contain ```json ... ``` markers
                        if output.strip().startswith("```json"):
                            output = output.strip()[7:-3].strip()
                        output = json.loads(output)
                    except json.JSONDecodeError:
                        # If it's just a string, it's not what we expect.
                        logger.warning(f"LLM output for text description was a non-JSON string, which is not the expected format. Output: {output}")
                        return []

                if isinstance(output, dict) and 'spans' in output:
                    spans = output.get('spans')
                    if isinstance(spans, list):
                        return spans
                    else:
                        logger.warning(f"'spans' key in LLM output is not a list. Found: {type(spans)}")
                        return []
                
                logger.warning(f"LLM output for text description did not contain 'spans' key or is not a dict. Output: {output}")
                return []

            except (KeyError, TypeError) as e:
                logger.error(f"Error parsing LLM response for text description: {e}. Response: {response.get('output')}")
                return []

        results = await asyncio.gather(*[process_chunk(chunk) for chunk in text_chunks])
        return [item for sublist in results for item in sublist]

    async def generate_text(self, prompt: str, project_name: str, last_content: str = '') -> AsyncGenerator[str, None]:
        """生成文本"""
        if not prompt:
            raise ValueError("提示词不能为空")
        
        system_prompt = self._load_prompt('novel_writing.txt')
        system_prompt = system_prompt.replace('{context}', last_content)
        system_prompt = system_prompt.replace('{requirements}', prompt)
        
        async for token in self._process_text_stream(self.combine_prompts(system_prompt, prompt)):
            yield token

    async def continue_story(self, original_story: str, project_name: str, last_content: str = '') -> AsyncGenerator[str, None]:
        """续写故事"""
        if not original_story:
            raise ValueError("故事内容不能为空")

        system_prompt = self._load_prompt('story_continuation.txt')
        system_prompt = system_prompt.replace('{context}', last_content)
        
        async for token in self._process_text_stream(self.combine_prompts(system_prompt, original_story)):
            yield token

    def combine_prompts(self,system_prompt,text,project_name=""):
        """组合系统提示词和用户输入"""
        if project_name:
            text= f"项目名称: {project_name}\n\n{text}"
            
        message=[
            SystemMessage(content=system_prompt),
            HumanMessage(content=text)
        ]
        
        return message

    async def extract_character(self, text: str, project_name: str) -> dict:
        """从文本中提取人物信息"""
        if not text:
            raise ValueError("文本内容不能为空")
            
        system_prompt = self._load_prompt('character_extraction.txt')
        
        
         # 获取已有实体和锁定实体
        entities = ",".join(self.kg_service.inquire_entity_names(project_name))
        locked_entities =",".join(self.kg_service.get_locked_entities(project_name))
        
        # 填充提示词变量
        system_prompt = system_prompt.replace("{{entities}}", json.dumps(entities, ensure_ascii=False))
        system_prompt = system_prompt.replace("{{locked_entities}}", json.dumps(locked_entities, ensure_ascii=False))
        

        
        # 创建LangChain Agent
        agent = self._create_agent_executor( self.kg_service.get_tools())
 
        result_text =await agent.ainvoke(self.combine_prompts(system_prompt,text,project_name)) 
        
        final_answer = result_text.get('output') if isinstance(result_text, dict) else str(result_text)
        
        # 获取结果
        entities = json.loads(self.kg_service.inquire_entity_list(project_name))
        relationships = {
            entity['name']: json.loads(self.kg_service.inquire_entity_relationships(
                project_name=project_name,
                name=entity['name']
            )) 
            for entity in entities if isinstance(entity, dict) and 'name' in entity
        }
        
        self.kg_service.save_kg(project_name)
        
        return {
            'result': final_answer,
            'entities': entities,
            'relationships': relationships
        }

    async def _translate_prompt_batch(self, project_name: str, prompts: List[str], system_prompt: str, entities: List[dict]) -> List[str]:
        """
        批量翻译提示词
        Args:
            project_name: 项目名称
            prompts: 提示词列表
            system_prompt: 系统提示词模板
            entities: 实体信息列表
        Returns:
            翻译后的提示词列表
        """
        try:
            # 收集所有提示词中的实体或基底场景名称
            all_entity_names = set()
            all_scene_names = set()
            for prompt in prompts:
                entity_names = re.findall(r'\{([^}]+)\}', prompt)
                all_entity_names.update(entity_names)
                scene_names = re.findall(r'\$\$([^$]+)\$\$', prompt)
                all_scene_names.update(scene_names)

            # 找到对应的实体信息
            entity_infos = []
            for name in all_entity_names:
                for entity in entities:
                    if entity['name'] == name:
                        info_str = f"{entity['name']}：{entity.get('attributes', {}).get('description', '')}"
                        entity_infos.append(info_str)
                        break
            
            scene_dict = self.scene_service.get_scene_dict(project_name, all_scene_names)
            scene_infos = [f"{scene_name}:{scene_dict[scene_name]}" for scene_name in all_scene_names]

            # 复制系统提示词并替换实体信息
            current_system_prompt = system_prompt
            if entity_infos:
                current_system_prompt = current_system_prompt.replace('{entities}', '\n'.join(entity_infos))
            if scene_infos:
                current_system_prompt = current_system_prompt.replace('{scenes}', '\n'.join(scene_infos))

            # 将提示词分成更小的批次
            batch_size = 4
            translated_prompts = []
            total_batches = (len(prompts) + batch_size - 1) // batch_size
            
            for batch_index in range(total_batches):
                start_idx = batch_index * batch_size
                end_idx = min(start_idx + batch_size, len(prompts))
                batch_prompts = prompts[start_idx:end_idx]
                
                # 构建编号的提示词列表
                numbered_prompts = []
                for i, prompt in enumerate(batch_prompts, start_idx + 1):
                    numbered_prompts.append(f"{i}. {prompt}")
                prompts_str = '\n'.join(numbered_prompts)
                
                logging.info(f"处理第 {batch_index + 1}/{total_batches} 批提示词，包含 {len(batch_prompts)} 个提示词")
                logging.info(f"当前编号的提示词列表：\n{prompts_str}")
                
                # 使用 LangChain 消息构建
                messages = [
                    SystemMessage(content=current_system_prompt),
                    HumanMessage(content=prompts_str)
                ]
                
                # 使用 LangChain 调用 LLM
                response = await self.llm.ainvoke(messages)
                result = response.content.strip()
                batch_results = []
                
                # 使用正则表达式匹配编号的提示词
                pattern = r'^\d+\.\s*(.+)$'
                for line in result.split('\n'):
                    line = line.strip()
                    if line:
                        match = re.match(pattern, line)
                        if match:
                            batch_results.append(match.group(1).strip())
                
                # 确保当前批次的翻译结果数量正确
                if len(batch_results) != len(batch_prompts):
                    logger.info(batch_results)
                    logger.info(batch_prompts)
                    raise Exception(f"批次 {batch_index + 1} 的翻译结果数量 ({len(batch_results)}) 与输入数量 ({len(batch_prompts)}) 不匹配，请重试！")
                
                translated_prompts.extend(batch_results)
                
                # 在批次之间添加短暂延迟，避免触发速率限制
                if batch_index < total_batches - 1:
                    await asyncio.sleep(0.5)
            
            # 最终验证
            if len(translated_prompts) != len(prompts):
                raise Exception(f"总翻译结果数量 ({len(translated_prompts)}) 与输入数量 ({len(prompts)}) 不匹配")
            
            return translated_prompts
            
        except Exception as e:
            logging.error(f'批量翻译提示词失败: {str(e)}')
            raise

    async def _translate_prompt_batch_reference_image(self, project_name: str, prompts: List[str], system_prompt: str, entities: List[dict]) -> List[str]:
        """
        批量翻译提示词
        Args:
            project_name: 项目名称
            prompts: 提示词列表
            system_prompt: 系统提示词模板
            entities: 实体信息列表
        Returns:
            翻译后的提示词列表
        """
        try:
            # 找到对应的实体信息
            entity_infos = {}
            for entity in entities:
                info_str = entity.get('attributes', {}).get('description', '')
                info_str_list=info_str.split(",")
                info_str=info_str_list[0]

                entity_infos[entity['name']]=info_str
                
            scene_infos = self.scene_service.load_scenes(project_name)
            for scene_name,des in scene_infos.items():
                des_list=des.split(",")
                scene_infos[scene_name]=des_list[0]
           
            # 替换每个prompt中的实体标记
            processed_prompts = []
            for prompt in prompts:
                entity_names = re.findall(r'\{([^}]+)\}', prompt)
                scene_names = re.findall(r'\[([^$]+)\]', prompt)
                processed_prompt = prompt
                for name in entity_names:
                    if name in entity_infos:
                        n="{"+name+"}"
                        new_n=f"{name}[{entity_infos[name]}]"
                        processed_prompt = processed_prompt.replace(n, new_n)
                        
                for scene_name in scene_names:
                    if scene_name in scene_infos:
                        n="["+scene_name+"]"
                        new_n=f"{scene_name}[{scene_infos[scene_name]}]"
                        processed_prompt = processed_prompt.replace(n, new_n)

                processed_prompts.append(processed_prompt)

            # 复制系统提示词
            current_system_prompt = system_prompt

            # 将提示词分成更小的批次
            batch_size = 4
            translated_prompts = []
            total_batches = (len(processed_prompts) + batch_size - 1) // batch_size
            
            for batch_index in range(total_batches):
                start_idx = batch_index * batch_size
                end_idx = min(start_idx + batch_size, len(processed_prompts))
                batch_prompts = processed_prompts[start_idx:end_idx]
                
                # 构建编号的提示词列表
                numbered_prompts = []
                for i, prompt in enumerate(batch_prompts, start_idx + 1):
                    numbered_prompts.append(f"{i}. {prompt}")
                prompts_str = '\n'.join(numbered_prompts)
                
                logging.info(f"处理第 {batch_index + 1}/{total_batches} 批提示词，包含 {len(batch_prompts)} 个提示词")
                logging.info(f"当前编号的提示词列表：\n{prompts_str}")
                
                # 使用 LangChain 消息构建
                messages = [
                    SystemMessage(content=current_system_prompt),
                    HumanMessage(content=prompts_str)
                ]
                
                # 使用 LangChain 调用 LLM
                response = await self.llm.ainvoke(messages)
     
                result = response.content.strip()
                batch_results = []
                
                try:
                    # 清理从LLM响应中可能存在的多余字符和markdown标记
                    if result.strip().startswith("```json"):
                        clean_result = result.strip()[7:-3].strip()
                    else:
                        clean_result = result

                    # 解析JSON响应
                    llm_output = json.loads(clean_result)

                    if not isinstance(llm_output, list):
                        raise ValueError("LLM响应不是预期的列表格式。")

                    # 按ID排序以确保顺序正确
                    llm_output.sort(key=lambda x: x.get('id', 0))
                    
                    # 提取'answer'字段
                    for item in llm_output:
                        if isinstance(item, dict) and 'answer' in item:
                            batch_results.append(item['answer'])
                        else:
                            logging.warning(f"跳过批处理响应中的格式错误项: {item}")

                except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                    logging.error(f"为批次 {batch_index + 1} 解析或处理LLM JSON响应失败。错误: {e}\n响应:\n{result}")
                    # 让其落空，以便后续的长度检查能够捕获到此错误
                    pass
                
                # 确保当前批次的翻译结果数量正确
                if len(batch_results) != len(batch_prompts):
                    raise Exception(f"批次 {batch_index + 1} 的翻译结果数量 ({len(batch_results)}) 与输入数量 ({len(batch_prompts)}) 不匹配")
                
                translated_prompts.extend(batch_results)
                
                # 在批次之间添加短暂延迟，避免触发速率限制
                if batch_index < total_batches - 1:
                    await asyncio.sleep(0.5)
            
            # 最终验证
            if len(translated_prompts) != len(prompts):
                raise Exception(f"总翻译结果数量 ({len(translated_prompts)}) 与输入数量 ({len(prompts)}) 不匹配")
            
            return translated_prompts
            
        except Exception as e:
            logging.error(f'批量翻译提示词失败: {str(e)}')
            raise

    async def translate_prompt(self, project_name: str, prompts: List[str]) -> List[str]:
        """
        翻译提示词列表
        Args:
            project_name: 项目名称
            prompts: 提示词列表
        Returns:
            翻译后的提示词列表
        """
        try:
            reference_image_mode=self.config['comfyui'].get('reference_image_mode', True)
            
            if reference_image_mode:
                system_prompt=self._load_prompt('prompt_translation_kontext.txt')
            else:   
                system_prompt = self._load_prompt('prompt_translation.txt')

            # 从知识图谱中获取所有实体信息
            entities_json = self.kg_service.inquire_entity_list(project_name)
            entities = json.loads(entities_json)

            # 将提示词列表按组进行切分
            batch_size = 8
            batches = [prompts[i:i + batch_size] for i in range(0, len(prompts), batch_size)]

            # 并行处理每个批次
            tasks = []
            for batch in batches:
                if reference_image_mode:
                    tasks.append(self._translate_prompt_batch_reference_image(project_name, batch, system_prompt, entities))
                else:
                    tasks.append(self._translate_prompt_batch(project_name, batch, system_prompt, entities))

            # 执行所有任务
            results = await asyncio.gather(*tasks)

            # 将所有批次的结果合并
            translated_prompts = []
            for batch_result in results:
                translated_prompts.extend(batch_result)

            return translated_prompts

        except Exception as e:
            logging.error(f'翻译提示词失败: {str(e)}')
            raise