import time
import streamlit as st
from src.config.role import ROLE_CN
from src.graph.builder import build_werewolf_graph
from src.recorder.logger import GameRecorder

st.set_page_config(page_title="狼人殺 AI 觀戰室", page_icon="🐺", layout="wide")

ROLE_ICON = {
    "werewolf": "🐺",
    "villager": "👨‍🌾",
    "seer": "🔮",
    "witch": "🧪",
    "hunter": "🔫"
}

# ==========================================
# 1. 側邊欄：上帝視角控制面板
# ==========================================
with st.sidebar:
    st.title("🎛️ 觀戰控制台")
    god_mode = st.toggle("👁️ 開啟上帝視角（看底牌與內心戲）", value=True)
    step_delay = st.slider("⏱️ 節點播放間隔 (秒)", min_value=0.0, max_value=3.0, value=0.5, step=0.5)
    start_btn = st.button("🚀 開啟新一局對戰", type="primary", use_container_width=True)
    st.divider()
    potion_box = st.empty()  # 展示女巫藥水與預言家查驗狀態


# ==========================================
# 2. 渲染組件函數：9人座位卡 + 實時事件流
# ==========================================
def render_player_seats(container, state: dict, show_secret: bool):
    """渲染 3x3 圓桌玩家狀態卡片"""
    players = state.get("players", {})
    if not players:
        return

    with container.container():
        st.subheader(f"🪑 場上座位狀態（第 {state.get('day', 0)} 天）")
        cols = st.columns(3)
        for idx, (pid, p) in enumerate(players.items()):
            alive = p["alive"]
            role_key = p["role"]
            role_label = f"{ROLE_ICON.get(role_key, '👤')} {ROLE_CN[role_key]}" if (
                        show_secret or not alive) else "❓ 未知身份"
            status_badge = "🟢 存活" if alive else "💀 出局"
            bg_color = "#1e293b" if alive else "#27171a"
            border_color = "#3b82f6" if alive else "#ef4444"

            with cols[idx % 3]:
                st.markdown(
                    f"""
                    <div style="border:2px solid {border_color}; background:{bg_color}; 
                                border-radius:10px; padding:12px; margin-bottom:10px; color:white;">
                        <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:16px;">
                            <span>{pid}</span>
                            <span>{status_badge}</span>
                        </div>
                        <div style="margin-top:6px; font-size:14px; color:#cbd5e1;">
                            身份：{role_label}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


def render_event_feed(container, state: dict, show_secret: bool):
    """渲染右側聊天氣泡與戰況時間軸"""
    events = state.get("event_logs", [])
    with container.container():
        st.subheader("🎬 實時博弈紀錄")
        for ev in events:
            etype = ev["type"]
            day = ev["day"]

            # 1. 狼人加密夜聊（僅上帝視角可見）
            if etype == "wolf_chat":
                if show_secret:
                    with st.chat_message("user", avatar="🐺"):
                        st.markdown(
                            f"**[第{day}夜·狼隊加密] {ev['actor']}**：{ev['message']} *(建議刀：`{ev['target']}`)*")
                        st.caption(f"💭 內心盤算：{ev['thought']}")

            # 2. 夜晚神職結算（僅上帝視角可見）
            elif etype == "night_action" and show_secret:
                st.info(f"🌙 **[第{day}夜·暗箱操作] {ev['title']}**：{ev['detail']}")

            # 3. 天亮公開死訊宣告
            elif etype == "day_announce":
                st.warning(f"☀️ **[第{day}天·上帝宣告]** {ev['detail']}")

            # 4. 白天玩家發言
            elif etype == "speech":
                role_tag = f"（{ev['role']}）" if show_secret else ""
                with st.chat_message("assistant", avatar="🗣️"):
                    st.markdown(f"**{ev['actor']}{role_tag}**：{ev['speech']}")
                    if show_secret and ev.get("thought"):
                        with st.expander("💭 查看 AI 內心真實策略 (Thought)", expanded=False):
                            st.write(ev["thought"])

            # 5. 放逐投票結果
            elif etype == "vote":
                with st.expander(f"🗳️ 第 {day} 天（第 {ev['round']} 輪）投票明細 — 結果：{ev['result']}", expanded=True):
                    for line in ev["details"]:
                        st.markdown(f"- {line}")


# ==========================================
# 3. 主界面佈局與 LangGraph 流式驅動
# ==========================================
st.title("🐺 狼人殺多智能體 (LangGraph) 實時觀戰台")
left_col, right_col = st.columns([5, 7], gap="large")

with left_col:
    seats_placeholder = st.empty()
with right_col:
    feed_placeholder = st.empty()

if start_btn:
    app = build_werewolf_graph()
    recorder = GameRecorder(log_dir="logs")
    final_state = None

    with st.spinner("🎲 正在分配身份並啟動 LangGraph 狀態機..."):
        # 使用 stream_mode="values" 逐步接收每個節點執行後的完整 GameState
        for step_state in app.stream({}, stream_mode="values"):
            final_state = step_state

            # 刷新左側座位與側邊欄神職狀態
            render_player_seats(seats_placeholder, step_state, god_mode)
            if god_mode and "witch_potions" in step_state:
                potions = step_state["witch_potions"]
                checks = step_state.get("seer_checks", {})
                potion_box.markdown(
                    f"### 🔮 神職機密面板\n"
                    f"- **女巫解藥**：{'🟢 可用' if potions.get('save') else '⚫ 已用'}\n"
                    f"- **女巫毒藥**：{'🟢 可用' if potions.get('poison') else '⚫ 已用'}\n"
                    f"- **預言家查驗**：`{checks if checks else '暫無'}`"
                )

            # 刷新右側事件流
            render_event_feed(feed_placeholder, step_state, god_mode)
            if step_delay > 0:
                time.sleep(step_delay)

    # 遊戲結束展示橫幅並自動導出戰報
    if final_state and final_state.get("winner"):
        winner_str = "🎉 好人陣營獲勝！" if final_state["winner"] == "good" else "🐺 狼人陣營獲勝！"
        st.balloons()
        st.success(f"🏁 遊戲結束！{winner_str}")
        recorder.save_all(final_state)
        st.caption(f"📄 完整戰報已自動保存至 `{recorder.md_path}`")