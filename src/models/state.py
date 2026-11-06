from typing import TypedDict, List, Dict, Optional, Annotated
import operator

from src.models.player import Player

class GameState(TypedDict):
    day: int
    phase: str                                # init, night, day_announce, speech, vote, end
    players: Dict[str, Player]                # 所有玩家状态
    # 公共信息（所有人可见）
    death_announcements: Annotated[List[str], operator.add]  # 每日公开死讯
    public_speeches: Annotated[List[dict], operator.add]
    vote_history: Annotated[List[dict], operator.add]

    # 新增：狼人夜晚加密频道记录（仅狼人可见）
    wolf_chat_history: Annotated[List[dict], operator.add]

    # 关键：全量上帝视角事件流（用于生成 Markdown 复盘战报）
    event_logs: Annotated[List[dict], operator.add]

    # 机密信息（仅上帝和对应角色可见）
    night_kill_target: Optional[str]          # 狼人今晚刀的目标
    witch_potions: Dict[str, bool]            # {"save": True, "poison": True}
    witch_potions_info: Dict[str, str]        # {"save": "2号", "poison": "3号"}
    seer_checks: Dict[str, str]               # 预言家查验记录 {"2号": "狼人"}
    night_deaths: List[str]                   # 今晚最终死亡名单
    winner: Optional[str]                     # "werewolf" | "good" | None

    # 新增：平票 PK 状态控制
    vote_round: int  # 1 表示常规首轮投票，2 表示平票后的二次 PK 投票
    pk_candidates: List[str]  # 进入平票 PK 台的玩家列表，如 ["2号", "5号"]