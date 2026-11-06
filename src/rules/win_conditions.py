import random
from typing import Dict, Optional, List

from src.models.player import Player
from src.models.state import GameState
from src.config.role import ROLE_CN


def get_alive_ids(players: Dict[str, Player], exclude_role: Optional[str] = None) -> List[str]:
    """获取当前存活的玩家ID列表，可选排除特定角色"""
    return [
        pid for pid, p in players.items()
        if p["alive"] and (exclude_role is None or p["role"] != exclude_role)
    ]

def find_role_player(players: Dict[str, Player], role: str) -> Optional[Player]:
    """查找特定神职玩家（预言家/女巫/猎人）"""
    for p in players.values():
        if p["role"] == role:
            return p
    return None

def check_winner(players: Dict[str, Player]) -> Optional[str]:
    """
    胜负判定（标准 9 人局通常采用【屠边规则】）：
    1. 狼人全灭 -> 好人获胜 ("good")
    2. 村民全灭 或 神职全灭 -> 狼人获胜 ("werewolf")
    """
    alive_wolves = [p for p in players.values() if p["alive"] and p["role"] == "werewolf"]
    alive_villagers = [p for p in players.values() if p["alive"] and p["role"] == "villager"]
    alive_gods = [p for p in players.values() if p["alive"] and p["role"] in ("seer", "witch", "hunter")]

    if len(alive_wolves) == 0:
        print("🎉 [胜负判定] 场上狼人全部出局，好人阵营获胜！")
        return "good"
    if len(alive_villagers) == 0:
        print("🐺 [胜负判定] 场上平民全部出局（屠民成功），狼人阵营获胜！")
        return "werewolf"
    if len(alive_gods) == 0:
        print("🐺 [胜负判定] 场上神职全部出局（屠神成功），狼人阵营获胜！")
        return "werewolf"
    return None



def get_player_context(
    state: GameState,
    player_id: str,
    current_day_speeches: Optional[List[dict]] = None,
    current_night_wolf_chats: Optional[List[dict]] = None
) -> str:
    """
    【视野隔离核心函数】
    根据 player_id 的真实身份，组装专属于他一个人的上下文信息。
    绝不泄露其他角色的私密状态！
    """
    players = state["players"]
    me = players[player_id]
    my_role = me["role"]

    alive_ids = [pid for pid, p in players.items() if p["alive"]]
    dead_ids = [pid for pid, p in players.items() if not p["alive"]]

    lines = [
        f"【基本局势】当前是第 {state['day']} 天。",
        f"【你的身份】你是 {player_id}，底牌身份是：【{ROLE_CN[my_role]}】。",
        f"【存活玩家】({len(alive_ids)}人): {', '.join(alive_ids)}",
        f"【已出局玩家】({len(dead_ids)}人): {', '.join(dead_ids) if dead_ids else '无'}",
    ]

    # 1. 按角色注入【专属机密记忆】
    if my_role == "werewolf":
        teammates = [
            f"{pid}({'存活' if p['alive'] else '出局'})"
            for pid, p in players.items()
            if p["role"] == "werewolf" and pid != player_id
        ]
        lines.append(f"【狼人机密视野】你的狼队友是：{', '.join(teammates)}。夜晚你们共享袭击目标，白天你可以选择悍跳神职、倒钩或冲票。")

        # 合并历史夜聊与今晚实时夜聊
        all_wolf_chats = list(state.get("wolf_chat_history", []))
        if current_night_wolf_chats:
            all_wolf_chats.extend(current_night_wolf_chats)

        if all_wolf_chats:
            lines.append("\n【狼人队内加密讨论记录（仅狼队可见）】")
            for wc in all_wolf_chats[-9:]:  # 保留最近几晚的战术记录
                lines.append(f"  - [第{wc['day']}夜] {wc['wolf']} 对队友说: “{wc['message']}” (建议刀: {wc['target']})")

    elif my_role == "seer":
        checks = state.get("seer_checks", {})
        check_str = ", ".join([f"{k}是{'狼人' if v == 'werewolf' else '好人'}" for k, v in checks.items()])
        lines.append(f"【预言家机密视野】你过去的查验记录：{check_str if check_str else '暂无'}。")

    elif my_role == "witch":
        potions = state.get("witch_potions", {})
        lines.append(
            f"【女巫机密视野】你的药水剩余状态：解药={'有' if potions.get('save') else '已用'}，毒药={'有' if potions.get('poison') else '已用'}。")

    # 2. 注入【公共死讯记录】
    if state.get("death_announcements"):
        lines.append("\n【历史死讯公告】")
        for msg in state["death_announcements"]:
            lines.append(f"  - {msg}")

    # 3. 注入【公共投票记录】
    if state.get("vote_history"):
        lines.append("\n【历史投票记录】")
        for vh in state["vote_history"]:
            vote_pairs = ", ".join([f"{k}->{v}" for k, v in vh["votes"].items()])
            lines.append(f"  - 第{vh['day']}天投票: {vote_pairs} | 最终放逐: {vh['exiled']}")

    # 4. 注入【历史与当日公开发言】
    all_speeches = list(state.get("public_speeches", []))
    if current_day_speeches:
        all_speeches.extend(current_day_speeches)

    if all_speeches:
        lines.append("\n【场上公开发言记录】")
        for sp in all_speeches[-18:]:  # 截取最近18条发言防止上下文过长
            lines.append(f"  - [第{sp['day']}天] {sp['speaker']}: “{sp['content']}”")

    return "\n".join(lines)



def validate_target(chosen: str, candidates: List[str]) -> str:
    """兜底校验：防止 LLM 输出 '玩家2号' 或已死玩家，若匹配失败则随机兜底"""
    chosen = chosen.strip()
    if chosen in candidates:
        return chosen
    # 尝试模糊匹配（比如 LLM 返回了 "我选2号"，提取其中的 "2号"）
    for c in candidates:
        if c in chosen:
            return c
    fallback = random.choice(candidates)
    print(f"  ⚠️ [系统修正] LLM 输出的目标 '{chosen}' 不在合法候选列表 {candidates} 中，已自动修正为 {fallback}")
    return fallback