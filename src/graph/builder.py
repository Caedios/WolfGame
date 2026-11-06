from langgraph.constants import START, END
from langgraph.graph import StateGraph

from src.graph.routers import route_after_day_settle, route_after_vote
from src.graph.nodes import *
from src.models.state import GameState


def build_werewolf_graph():
    workflow = StateGraph(GameState)

    # 1. 注册所有节点
    workflow.add_node("init_game", init_game_node)
    workflow.add_node("night_wolf", night_wolf_node)
    workflow.add_node("night_seer", night_seer_node)
    workflow.add_node("night_witch", night_witch_node)
    workflow.add_node("day_settle", day_settle_node)
    workflow.add_node("day_speech", day_speech_node)
    workflow.add_node("pk_speech", pk_speech_node)
    workflow.add_node("day_vote", day_vote_node)

    # 2. 连接固定边（夜晚流水线）
    workflow.add_edge(START, "init_game")
    workflow.add_edge("init_game", "night_wolf")
    workflow.add_edge("night_wolf", "night_seer")
    workflow.add_edge("night_seer", "night_witch")
    workflow.add_edge("night_witch", "day_settle")

    # 3. 连接条件边 1：天亮结算死讯后检查游戏是否结束
    workflow.add_conditional_edges(
        "day_settle",
        route_after_day_settle,
        {
            "game_over": END,
            "continue_to_speech": "day_speech"
        }
    )

    # 4. 发言结束后进入投票
    workflow.add_edge("day_speech", "day_vote")

    # PK 发言结束后，直接回到 day_vote 进行第二轮投票
    workflow.add_edge("pk_speech", "day_vote")

    # 5. 连接条件边 2：投票放逐后检查游戏是否结束，未结束则跳回 night_wolf 循环
    workflow.add_conditional_edges(
        "day_vote",
        route_after_vote,
        {
            "game_over": END,
            "tie_pk": "pk_speech",  # 首轮平票 -> 进入 PK 发言
            "next_night": "night_wolf"  # 正常放逐 或 二轮平票平安日 -> 进入黑夜
        }
    )

    return workflow.compile()



