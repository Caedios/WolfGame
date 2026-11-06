import json

from pydantic import BaseModel, Field

def get_json_schema_hint(model: type[BaseModel]) -> str:
    schema = model.model_json_schema()
    return f"请严格按以下 JSON Schema 输出，只输出 JSON，不要任何解释或 markdown 代码块：\n{json.dumps(schema, ensure_ascii=False, indent=2)}"

class TargetDecision(BaseModel):
    thought: str = Field(description="结合场上局势、你的身份和发言记录，进行简短的私密策略思考（其他玩家不可见）")
    target_id: str = Field(description="你最终选择的目标玩家编号，必须严格从候选列表中选择，例如 '2号'")

class SpeechDecision(BaseModel):
    thought: str = Field(description="你发言前的内心真实策略思考，如：我是狼人我要伪装好人，或我是预言家我要报查验（其他玩家不可见）")
    speech: str = Field(description="你在白天公开发表的言论，控制在 50~120 字以内，不要暴露自己是个AI")

class WitchDecision(BaseModel):
    thought: str = Field(description="你作为女巫的私密策略思考，分析今晚局势和用药取舍（其他玩家不可见）")
    use_antidote: bool = Field(description="是否使用解药救回今晚被狼人袭击的玩家")
    use_poison: bool = Field(description="是否使用毒药毒杀一名玩家")
    target_id: str = Field(
        default="",
        description="若使用解药，填写解救目标玩家编号（如 '2号'）；若使用毒药，填写毒杀目标玩家编号（如 '2号'）；若不使用解药和毒药，填空字符串"
    )

class WolfDiscussion(BaseModel):
    thought: str = Field(description="你个人的局势判断与内心盘算")
    team_message: str = Field(description="你在狼人加密频道对队友说的话（好人不可见）。可以分析谁是神职，并和队友配合明天白天的战术（如谁悍跳预言家、谁倒钩）")
    target_id: str = Field(description="你建议今晚袭击的目标玩家编号，如 '4号'")