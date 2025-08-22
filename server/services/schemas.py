from __future__ import annotations

import json
from typing import Dict, List, Optional
from pydantic import BaseModel, RootModel, Field, ConfigDict


# 场景提取：键值对映射（场景名 -> 英文描述）
class SceneExtractionResult(RootModel[Dict[str, str]]):
    model_config = ConfigDict(json_schema_extra={
        "title": "SceneExtractionResult",
        "description": "Map of scene name (Chinese allowed) to concise English visual description. Must describe environment only; no characters.",
        "examples": [
            {"教学楼台阶": "Concrete steps leading to a campus building entrance, metal handrails, bulletin board"}
        ]
    })


# 文本分镜提示词：spans 列表
class TextSpan(BaseModel):
    content: str = Field(..., description="原始文本片段内容", examples=["林小夏脸一红，低声嘟囔……"])
    base_scene: str = Field(..., description="基底场景名称（来自场景库）", examples=["教学楼台阶"])
    scene: str = Field(..., description="不含基底场景的画面描述，优先动词，保留关键形容词；可包含用 {} 包裹的人名", examples=["{林小夏}脸红, 低声嘟囔"])


class TextDescResult(BaseModel):
    spans: List[TextSpan] = Field(..., description="分镜片段列表")
    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "spans": [
                    {"content": "林小夏脸一红，低声嘟囔……", "base_scene": "教学楼台阶", "scene": "{林小夏}脸红, 低声嘟囔"}
                ]
            }
        ]
    })


# 普通提示词翻译：字符串列表
class PromptList(RootModel[List[str]]):
    model_config = ConfigDict(json_schema_extra={
        "title": "PromptList",
        "description": "Translated prompts list in English; each item is a concise, comma-separated prompt without trailing period.",
        "examples": [[
            "A young woman, soft daylight, medium shot, street background, casual outfit, cinematic color grading"
        ]]
    })


# Kontext 提示词翻译：对象数组
class PromptKontextItem(BaseModel):
    id: int = Field(..., ge=1, description="输入提示词的序号", examples=[1])
    convert_entity: str = Field(..., description="实体与场景的简短标识映射/归纳", examples=["驾驶舱->the cockpit, 林远->the male commander"])
    thinking: str = Field(..., description="简要分析过程：如何将场景拆分为1-4个命令式步骤及动词选择原因", examples=["Identify subject and cockpit; keep composition; adjust pose; add tapping gesture"])
    answer: str = Field(..., description="最终英文命令式指令（1-4句）", examples=["Place the male commander inside the cockpit. Change the pose to gaze out of the window. Adjust the right hand to tap the navigation console."])


class PromptKontextList(RootModel[List[PromptKontextItem]]):
    model_config = ConfigDict(json_schema_extra={
        "title": "PromptKontextList",
        "description": "List of FLUX.1 Kontext edit instructions per input item.",
        "examples": [[
            {
                "id": 1,
                "convert_entity": "驾驶舱->the cockpit, 林远->the male commander",
                "thinking": "Identify subject and cockpit; keep composition; adjust pose; add tapping gesture",
                "answer": "Place the male commander inside the cockpit. Change the pose to gaze out of the window. Adjust the right hand to tap the navigation console."
            }
        ]]
    })


def append_output_schema_to_prompt(prompt: str, model_type: type[BaseModel]) -> str:
    """在提示词末尾追加 JSON Schema 说明，供 LLM 严格对齐输出。
    """
    # pydantic v2: model_json_schema()
    schema_dict = model_type.model_json_schema()
    schema_json = json.dumps(schema_dict, ensure_ascii=False)
    suffix = "\n-OutputFormat：请严格根据提供的Json Schema返回结果\n" + schema_json
    return prompt.rstrip() + suffix


# 角色提取总结
class RelationshipChange(BaseModel):
    type: str = Field(..., description="关系类型", examples=["朋友", "同事", "父女"])
    source: str = Field(..., description="源实体名称", examples=["林远"])
    target: str = Field(..., description="目标实体名称", examples=["林小夏"])
    attributes: Optional[Dict[str, str]] = Field(default=None, description="可选的关系属性字典", examples=[[{"since": "高中"}]])


class CharacterExtractionSummary(BaseModel):
    added_entities: List[str] = Field(default_factory=list, description="本次新增的实体名称列表", examples=[["林远"]])
    updated_entities: List[str] = Field(default_factory=list, description="本次更新属性的实体名称列表", examples=[["林小夏"]])
    new_relationships: List[RelationshipChange] = Field(default_factory=list, description="本次新增的关系列表")
    updated_relationships: List[RelationshipChange] = Field(default_factory=list, description="本次更新属性的关系列表")
    notes: Optional[str] = Field(default=None, description="其他备注或决策说明", examples=["跳过锁定实体的属性更新"])
    model_config = ConfigDict(json_schema_extra={
        "title": "CharacterExtractionSummary",
        "description": "A compact summary of KG changes performed via tools during character extraction.",
    }) 