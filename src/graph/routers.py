from src.models.state import GameState


def route_after_day_settle(state: GameState) -> str:
    """天亮结算后：如果分出胜负则结束，否则进入白天发言"""
    if state.get("winner") is not None:
        return "game_over"
    return "continue_to_speech"

def route_after_vote(state: GameState) -> str:
    """投票后三路分支路由：游戏结束 / 首轮平票进PK / 进入下一夜"""
    if state.get("winner") is not None:
        return "game_over"
    # 如果 pk_candidates 不为空，说明刚刚发生了第一轮平票，需要去 PK 发言
    if state.get("pk_candidates"):
        return "tie_pk"
    return "next_night"

