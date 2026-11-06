from typing import List, Type, TypeVar

import json_repair
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from pydantic import BaseModel

from src.config.llm import get_llm
from src.models.schemas import TargetDecision, SpeechDecision, WolfDiscussion, get_json_schema_hint, WitchDecision

T = TypeVar("T", bound=BaseModel)

class PlayerAgent:
    def __init__(self):
        self.llm = get_llm()
        self.target_chain = self.llm.with_structured_output(TargetDecision, method="json_mode")
        self.speech_chain = self.llm.with_structured_output(SpeechDecision, method="json_mode")
        self.wolf_chain = self.llm.with_structured_output(WolfDiscussion, method="json_mode")
        self.witch_chain = self.llm.with_structured_output(WitchDecision, method="json_mode")

    def _invoke_structured(self, messages: List[BaseMessage], schema_cls: Type[T]) -> T:
        """
        核心容错调用：让 LLM 输出 JSON 文本 -> 用 json_repair 自动修复内部未转义引号 -> 转为 Pydantic 对象
        """
        response = self.llm.invoke(messages)
        raw_text = response.content

        # json_repair.loads 会自动把 {"thought": "...表示"可以听"..."} 修复为合法字典！
        repaired_dict = json_repair.loads(raw_text)

        # 如果修复后依然缺字段，给出安全默认值兜底，防止整局游戏崩溃
        if not isinstance(repaired_dict, dict):
            repaired_dict = {}

        return schema_cls.model_validate(repaired_dict)

    def wolf_discuss(self, context: str, candidates: List[str], is_last: bool) -> WolfDiscussion:
        hint = "你是今晚最后发言的尾狼，请综合队友意见做最终拍板。" if is_last else "请向狼队友提议今晚刀谁及明天白天的悍跳配合战术。"
        message = [
            SystemMessage(
                content=f"你正在参与9人局狼人杀夜晚【狼队加密讨论】环节。{hint}"
                + get_json_schema_hint(WolfDiscussion)
            ),
            HumanMessage(content=f"{context}\n\n【指令】请对队友发言，并从 {candidates} 中给出建议袭击目标。")
        ]
        return self._invoke_structured(message, WolfDiscussion)
        # return self.wolf_chain.invoke(message)

    def make_speech(self, pid: str, context: str, is_pk: bool = False) -> SpeechDecision:
        mode_str = "现在是【平票PK台】辩护发言，请全力表水拉票！" if is_pk else "现在轮到你白天公开发言，请根据底牌维护本阵营利益。"
        message = [
            SystemMessage(content=(
                    f"你正在参与9人局狼人杀。{mode_str}狼人需隐藏身份或悍跳，好人需找狼。"
                    + get_json_schema_hint(SpeechDecision)
            )),
            HumanMessage(content=f"{context}\n\n【指令】现在轮到你（{pid}）发言，请给出你的内心思考和公开发言内容。")
        ]
        return self._invoke_structured(message, SpeechDecision)
        # return self.speech_chain.invoke()


    def cast_vote(self, context: str, candidates: List[str]) -> TargetDecision:
        message = [
            SystemMessage(
                content="现在是狼人杀放逐投票环节，请结合白天发言和阵营利益投出你的一票。"
                + get_json_schema_hint(TargetDecision)
            ),
            HumanMessage(content=f"{context}\n\n【指令】请严格从候选名单 {candidates} 中选择一人投票。")
        ]
        return self._invoke_structured(message, TargetDecision)
        # return self.target_chain.invoke()

    def seer_check(self, context: str, candidates: List[str]) -> TargetDecision:
        message = [
            SystemMessage(content=(
                    "你正在参与一场9人局狼人杀（3狼3民，预言家、女巫、猎人，屠边规则）。\n"
                    "你现在的身份是【预言家】，属于好人阵营。现在是夜晚预言家验人阶段。\n"
                    "你的目标是查验一名玩家的阵营身份（结果只会是 'werewolf' 或 'good'），"
                    "请优先选择发言可疑、逻辑矛盾、或行为像狼人的玩家进行查验，以帮助好人阵营锁定狼人。\n"
                    "注意：你不知道谁是狼人，不要假设任何人的身份，只能依据场上发言和局势做判断。\n"
                    + get_json_schema_hint(TargetDecision)
            )),
            HumanMessage(
                content=f"{context}\n\n【指令】请从以下存活且尚未被你查验过的玩家中选择今晚的查验目标：{candidates}")
        ]
        return self._invoke_structured(message, TargetDecision)
        # return self.target_chain.invoke()

    def witch_poison(self, context: str, candidates: List[str], kill_target: str) -> WitchDecision:
        message = [
            SystemMessage(content=(
                    "你正在参与一场9人局狼人杀（3狼3民，预言家、女巫、猎人，屠边规则）。\n"
                    "你现在的身份是【女巫】，属于好人阵营。现在是夜晚女巫行动阶段。\n"
                    "你有一瓶解药和一瓶毒药，各只能使用一次。解药可以救回今晚被狼人袭击的玩家，"
                    "毒药可以毒死一名你怀疑是狼人的玩家。\n"
                    "请综合场上发言、投票记录和已知信息，谨慎决定是否使用解药、是否使用毒药以及毒杀目标。"
                    "注意：解药和毒药都很珍贵，不要轻易浪费；毒药不要毒到已知的好人。\n"
                    + get_json_schema_hint(WitchDecision)
            )),
            HumanMessage(content=(
                f"{context}\n\n"
                f"【信息】今晚被狼人袭击的玩家：{kill_target}\n"
                f"【信息】当前存活玩家：{candidates}\n"
                "【指令】请决定是否使用解药、是否使用毒药；若使用毒药，从存活玩家中选择毒杀目标。"
            ))
        ]
        return self._invoke_structured(message, WitchDecision)
        # return self.witch_chain.invoke()


    def hunt_kill(self, context: str, candidates: List[str]) -> TargetDecision:
        message = [
            SystemMessage(content=(
                    "你正在参与一场9人局狼人杀（3狼3民，预言家、女巫、猎人，屠边规则）。\n"
                    "你现在的身份是【猎人】，属于好人阵营。现在是夜晚猎人被狼人杀害后的开枪阶段。\n"
                    "你的目标是选择一名玩家开枪带走（结果只能是该玩家的编号/名字），"
                    "请优先选择发言可疑、逻辑矛盾、或行为像狼人的玩家开枪，以帮助好人阵营建立优势。\n"
                    "注意：你不知道谁是狼人，不要假设任何人的身份，只能依据场上发言和局势做判断。\n"
                    + get_json_schema_hint(TargetDecision)
            )),
            HumanMessage(
                content=f"{context}\n\n【指令】你今天死亡，现在可以开枪带走一名玩家。请从以下存活玩家中选择开枪目标：{candidates}")
        ]
        return self._invoke_structured(message, TargetDecision)