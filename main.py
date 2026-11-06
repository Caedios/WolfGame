from src.graph.builder import build_werewolf_graph
from src.recorder.logger import GameRecorder

def main():
    app = build_werewolf_graph()
    recorder = GameRecorder(log_dir="logs")

    # 启动状态机（传入空字典即可，init_game_node 会完成初始化）
    final_state = app.invoke({})

    # 游戏结束后自动生成 JSON 与 Markdown 复盘战报
    recorder.save_all(final_state)

    print("\n" + "=" * 45)
    print(f"🏁 游戏结束！共进行了 {final_state['day']} 天，最终获胜方：【{final_state['winner']}】")
    print("📊 终局存活名单：")
    for pid, p in final_state["players"].items():
        status = "🟢 存活" if p["alive"] else "💀 出局"
        print(f"  - {pid} ({p['role']}): {status}")
    print("=" * 45)

if __name__ == "__main__":
    main()