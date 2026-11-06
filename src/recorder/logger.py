import os
import json
from datetime import datetime
from typing import Dict, Any
from src.config.role import ROLE_CN


class GameRecorder:
    def __init__(self, log_dir: str = "logs"):
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.json_path = os.path.join(log_dir, f"game_{timestamp}.json")
        self.md_path = os.path.join(log_dir, f"report_{timestamp}.md")

    def save_all(self, final_state: Dict[str, Any]):
        """保存 JSON 原始数据与 Markdown 复盘战报"""
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(final_state, f, ensure_ascii=False, indent=2)

        md_content = self._render_markdown(final_state)
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n📄 [战报已导出] Markdown 复盘报告: {self.md_path}")
        print(f"💾 [数据已备份] JSON 状态明细: {self.json_path}")

    def _render_markdown(self, state: Dict[str, Any]) -> str:
        winner_cn = "🎉 好人阵营" if state.get("winner") == "good" else "🐺 狼人阵营"
        lines = [
            "# 🐺 狼人杀 AI 多智能体博弈复盘战报",
            f"- **对局生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **持续天数**：共 {state.get('day', 0)} 天",
            f"- **最终获胜方**：**{winner_cn}**\n",
            "## 📋 玩家底牌与终局状态",
            "| 玩家编号 | 真实底牌 | 所属阵营 | 终局状态 |",
            "| :---: | :---: | :---: | :---: |"
        ]

        for pid, p in state["players"].items():
            role_cn = ROLE_CN[p["role"]]
            camp = "狼人阵营" if p["role"] == "werewolf" else "好人阵营"
            status = "🟢 存活" if p["alive"] else "💀 出局"
            lines.append(f"| **{pid}** | {role_cn} | {camp} | {status} |")

        lines.append("\n---\n## 🎬 对局全流程上帝视角回放")

        current_day = 0
        for ev in state.get("event_logs", []):
            if ev["day"] != current_day:
                current_day = ev["day"]
                lines.append(f"\n## 📅 第 {current_day} 天")

            etype = ev["type"]
            if etype == "wolf_chat":
                lines.append(f"- 🐺 **[狼队夜聊] {ev['actor']}**：{ev['message']} *(提议刀：`{ev['target']}`)*")
                lines.append(f"  > 💭 *内心盘算：{ev['thought']}*")
            elif etype == "night_action":
                lines.append(f"- 🌙 **[夜晚结算] {ev['title']}**：{ev['detail']}")
            elif etype == "day_announce":
                lines.append(f"\n### ☀️ 第 {current_day} 天白天\n> 📢 **上帝宣告**：{ev['detail']}\n")
            elif etype == "speech":
                lines.append(f"#### 🗣️ {ev['actor']}（底牌：{ev['role']}）发言")
                lines.append(f"- **💭 真实内心戏**：*{ev['thought']}*")
                lines.append(f"- **📢 公开发言**：“{ev['speech']}”\n")
            elif etype == "vote":
                lines.append(f"#### 🗳️ 第 {ev['round']} 轮投票详情")
                for v_line in ev["details"]:
                    lines.append(f"- {v_line}")
                lines.append(f"- **⚖️ 放逐结果**：**{ev['result']}**\n")

        return "\n".join(lines)