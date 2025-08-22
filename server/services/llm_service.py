import os
import json
import logging
import re
import asyncio
from typing import AsyncGenerator, List, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler


from server.services.base_service import SingletonService
from server.services.kg_service import KGService
from server.services.scene_service import SceneService

logger = logging.getLogger(__name__)

# Pydantic 与结构化模型
from pydantic import BaseModel, ValidationError
from typing import Type
from server.services.schemas import (
    SceneExtractionResult,
    TextDescResult,
    PromptKontextList,
    PromptList,
    append_output_schema_to_prompt,
    CharacterExtractionSummary,
)
from json_repair import loads as json_repair_loads

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
        # 解析重试次数：允许在 config.llm.parse_retries 中覆盖，默认2
        self.parse_retries = int(self.config.get('llm', {}).get('parse_retries', 2) or 2)

        
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

    # 结构化输出工具
    async def _ainvoke_and_parse(self, system_prompt: str, user_content: str, model_type: Type[BaseModel], retries: int = 2) -> BaseModel:
        """调用 LLM 并将输出解析为指定 Pydantic 模型，带有限重试与 JSON 修复。"""
        if retries is None:
            retries = self.parse_retries
        attempt = 0
        last_err: Exception | None = None
        while attempt <= retries:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content)
            ]
            response = await self.llm.ainvoke(messages)
            raw = response.content if hasattr(response, 'content') else str(response)
            try:
                data = json_repair_loads(raw)
                return model_type.model_validate(data)
            except (ValidationError, Exception) as e:
                last_err = e
                logger.warning(f"结构化解析失败，第{attempt+1}次尝试: {e}")
                attempt += 1
                # 适度退避
                if attempt <= retries:
                    await asyncio.sleep(0.3 * attempt)
        # 最终失败
        if last_err:
            logger.error(f"结构化解析最终失败: {last_err}")
            raise last_err
        raise RuntimeError("结构化解析未知错误")

    def _build_system_prompt_with_schema(self, template_name: str, replacements: Dict[str, str], schema_model: Type[BaseModel]) -> str:
        """加载模板、替换变量，并自动追加 Schema。"""
        tpl = self._load_prompt(template_name)
        for k, v in replacements.items():
            tpl = tpl.replace(k, v)
        return append_output_schema_to_prompt(tpl, schema_model)

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
        split_pattern = r'(?<=[。！？])\s*'
        sentences = [s.replace('\n', ' ').strip() for s in re.split(split_pattern, text) if s.strip()]
        text = "\n".join(sentences)

        # 场景提取
        scene_names = self.scene_service.get_scene_names(project_name)
        system_prompt_for_scene = self._build_system_prompt_with_schema(
            "scene_extraction.txt",
            {"{scenes}": ",".join(scene_names)},
            SceneExtractionResult,
        )
        
        # 使用结构化调用
        scene_result = await self._ainvoke_and_parse(system_prompt_for_scene, f"项目名称: {project_name}\n\n{text}", SceneExtractionResult)
        self.scene_service.update_scenes(project_name, scene_result.root)

        # 文本描述生成（使用 Pydantic 结构化输出）
        entities_names=self.kg_service.inquire_entity_names(project_name)
        scene_names = self.scene_service.get_scene_names(project_name)
        current_text_desc_prompt = self._build_system_prompt_with_schema(
            "text_desc_prompt.txt",
            {"{scenes}": ",".join(scene_names), "{entities}": ",".join(entities_names)},
            TextDescResult,
        )
        
        # 处理文本块
        text_chunks = [text] if window_size <= 0 else [
            "\n".join(sentences[i:i+window_size]) 
            for i in range(0, len(sentences), window_size)
        ]
        
        async def process_chunk_structured(chunk: str):
            try:
                result: TextDescResult = await self._ainvoke_and_parse(current_text_desc_prompt, chunk, TextDescResult)
                return [span.model_dump() for span in result.spans]
            except Exception as e:
                logger.error(f"结构化解析文本描述失败: {e}")
                return []
        
        results = await asyncio.gather(*[process_chunk_structured(chunk) for chunk in text_chunks])
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
        # 追加输出Schema（总结 JSON）
        system_prompt = append_output_schema_to_prompt(system_prompt, CharacterExtractionSummary)
        

        
        # 创建LangChain Agent
        agent = self._create_agent_executor( self.kg_service.get_tools())
 
        result_text =await agent.ainvoke(self.combine_prompts(system_prompt,text,project_name))
        final_answer = result_text.get('output') if isinstance(result_text, dict) else result_text
        # 尝试解析总结 JSON
        summary = None
        try:
            if isinstance(final_answer, (dict, list)):
                summary = CharacterExtractionSummary.model_validate(final_answer)
            else:
                summary_data = json_repair_loads(str(final_answer))
                summary = CharacterExtractionSummary.model_validate(summary_data)
        except Exception as e:
            logger.warning(f"解析角色提取总结失败: {e}")
        
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
            'summary': summary.model_dump() if summary else None,
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
            scene_infos = [f"{scene_name}:{scene_dict.get(scene_name, '')}" for scene_name in all_scene_names if scene_dict.get(scene_name, '')]

            # 复制系统提示词并替换实体信息
            current_system_prompt = system_prompt
            if entity_infos:
                current_system_prompt = current_system_prompt.replace('{entities}', '\n'.join(entity_infos))
            if scene_infos:
                current_system_prompt = current_system_prompt.replace('{scenes}', '\n'.join(scene_infos))
            # 追加 Schema：普通翻译路径输出为按序号的英文行，但为避免解析歧义，这里采用数组形式返回
            current_system_prompt = append_output_schema_to_prompt(current_system_prompt, PromptList)

            # 将提示词分成更小的批次
            batch_size = 4
            translated_prompts = []
            total_batches = (len(prompts) + batch_size - 1) // batch_size
            
            for batch_index in range(total_batches):
                start_idx = batch_index * batch_size
                end_idx = min(start_idx + batch_size, len(prompts))
                batch_prompts = prompts[start_idx:end_idx]
                
                # 构建编号的提示词列表（作为用户内容）
                numbered_prompts = []
                for i, prompt in enumerate(batch_prompts, start_idx + 1):
                    numbered_prompts.append(f"{i}. {prompt}")
                prompts_str = '\n'.join(numbered_prompts) + f"\n\nReturn exactly {len(batch_prompts)} items in the array, one per input line, no extra or missing."
                
                logging.info(f"处理第 {batch_index + 1}/{total_batches} 批提示词，包含 {len(batch_prompts)} 个提示词")
                logging.info(f"当前编号的提示词列表：\n{prompts_str}")
                
                # 一次解析，必要时重试一次
                attempt = 0
                while True:
                    result_model: PromptList = await self._ainvoke_and_parse(current_system_prompt, prompts_str, PromptList, retries=self.parse_retries)
                    batch_results = list(result_model.root)
                    if len(batch_results) == len(batch_prompts):
                        break
                    attempt += 1
                    if attempt > 1:
                        raise Exception(f"批次 {batch_index + 1} 的翻译结果数量 ({len(batch_results)}) 与输入数量 ({len(batch_prompts)}) 不匹配")
                    prompts_str = '\n'.join(numbered_prompts) + f"\n\nIMPORTANT: Output MUST be a JSON array of {len(batch_prompts)} strings."
                
                translated_prompts.extend(batch_results)
                
                if batch_index < total_batches - 1:
                    await asyncio.sleep(0.5)
            
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
            # 追加 Schema：Kontext 输出是对象数组
            current_system_prompt = append_output_schema_to_prompt(current_system_prompt, PromptKontextList)

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
                prompts_str = '\n'.join(numbered_prompts) + f"\n\nReturn exactly {len(batch_prompts)} items, one per input line."
                
                logging.info(f"处理第 {batch_index + 1}/{total_batches} 批提示词，包含 {len(batch_prompts)} 个提示词")
                logging.info(f"当前编号的提示词列表：\n{prompts_str}")
                
                # 一次解析，必要时重试一次
                attempt = 0
                while True:
                    result_model: PromptKontextList = await self._ainvoke_and_parse(current_system_prompt, prompts_str, PromptKontextList, retries=self.parse_retries)
                    batch_results = [item.answer for item in result_model.root]
                    if len(batch_results) == len(batch_prompts):
                        break
                    attempt += 1
                    if attempt > 1:
                        raise Exception(f"批次 {batch_index + 1} 的翻译结果数量 ({len(batch_results)}) 与输入数量 ({len(batch_prompts)}) 不匹配")
                    prompts_str = '\n'.join(numbered_prompts) + f"\n\nIMPORTANT: Output MUST be a JSON array of {len(batch_prompts)} objects with id/convert_entity/thinking/answer."
                
                translated_prompts.extend(batch_results)
                
                if batch_index < total_batches - 1:
                    await asyncio.sleep(0.5)
            
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