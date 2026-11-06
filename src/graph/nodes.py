import random
from collections import Counter

from langchain_core.messages import SystemMessage, HumanMessage

from src.agents.player_agent import PlayerAgent
from src.models.schemas import TargetDecision, get_json_schema_hint, WitchDecision, SpeechDecision, WolfDiscussion
from src.config.llm import get_llm
from src.models.state import GameState
from src.config.role import ROLE_CN
from src.rules.win_conditions import get_alive_ids, find_role_player, check_winner, validate_target, get_player_context


agent = PlayerAgent()

def init_game_node(state: GameState) -> dict:
    """【初始化节点】洗牌分配 9 人身份"""
    roles = [
        "werewolf", "werewolf", "werewolf",
        "villager", "villager", "villager",
        "seer", "witch", "hunter"
    ]
    random.shuffle(roles)

    players = {}
    print("\n" + "= " *45)
    print("🎲 狼人杀 9 人局游戏开始！正在随机分配身份...")
    for i, role in enumerate(roles, 1):
        pid = f"{i}号"
        players[pid] = {"id": pid, "role": role, "alive": True}
        print(f"  - {pid}: {role}")
    print("= " *45)

    return {
        "day": 0,
        "players": players,
        "public_speeches": [],
        "vote_history": [],
        "wolf_chat_history": [],
        "event_logs": [],
        "night_kill_target": None,
        "witch_potions": {"save": True, "poison": True},
        "witch_potions_info": {"save": None, "poison": None},
        "seer_checks": {},
        "winner": None,

        # 平票控制参数
        "vote_round": 1,
        "pk_candidates": []
    }


def night_wolf_node(state: GameState) -> dict:
    """【夜晚-狼人行动】进入新的一夜，狼人选择袭击目标"""
    day = state["day"] + 1
    players = state["players"]
    logs = []

    print(f"\n🌙 ────── 第 {day} 夜降临，天黑请闭眼 ──────")

    # 找到当前存活的狼人，由存活的第一顺位狼人作为主刀代表调用 LLM
    alive_wolves = [pid for pid, p in players.items() if p["alive"] and p["role"] == "werewolf"]
    # 模拟逻辑：狼人优先随机刀一个非狼人玩家（后续阶段替换为 LLM 决策）
    candidates = get_alive_ids(players, exclude_role="werewolf")

    if not alive_wolves or not candidates:
        return {"day": day, "night_kill_target": None, "witch_potions_info": {"save": None, "poison": None}, "event_logs": logs}

    temp_state = dict(state)
    temp_state["day"] = day

    current_night_chats = []
    suggested_targets = []

    print(f"🐺 [狼队加密频道开启] 当前存活狼人: {', '.join(alive_wolves)}")
    for idx, wolf_id in enumerate(alive_wolves):
        # 传入 current_night_chats，让后发言的狼队友能看到前面队友刚说的话
        context = get_player_context(temp_state, wolf_id, current_night_wolf_chats=current_night_chats)
        is_last_wolf = (idx == len(alive_wolves) - 1)
        res: WolfDiscussion = agent.wolf_discuss(context, candidates, is_last_wolf)

        valid_t = validate_target(res.target_id, candidates)
        suggested_targets.append(valid_t)

        current_night_chats.append({
            "day": day,
            "wolf": wolf_id,
            "message": res.team_message,
            "target": valid_t
        })

        logs.append({
            "day": day,
            "type": "wolf_chat",
            "actor": wolf_id,
            "role": players[wolf_id]["role"],
            "thought": res.thought,
            "message": res.team_message,
            "target": valid_t
        })

        print(f"  💬 [{wolf_id} 加密发言]: “{res.team_message}” (提议刀 -> {valid_t})")

    # 结算狼队意见：少数服从多数；若3狼各投1人出现平票，则以最后总结的【尾狼】意见为准
    vote_counts = Counter(suggested_targets)
    most_common = vote_counts.most_common(1)
    if most_common:
        top_target, top_count = most_common[0]
    else:
        top_target, top_count = None, 0

    if top_count >= 2:
        final_target = top_target
        print(f"🐺 [狼队达成多数共识] 最终以 {top_count} 票决定袭击 -> 【{final_target}】")
    else:
        final_target = suggested_targets[-1]  # 尾狼拍板
        print(f"🐺 [狼队意见分歧，尾狼 {alive_wolves[-1]} 拍板] 最终决定袭击 -> 【{final_target}】")

    logs.append({
        "day": day,
        "type": "night_action",
        "title": "狼人袭击",
        "detail": f"狼人阵营最终锁定袭击目标：{final_target}"
    })

    # 重置当晚女巫动作状态
    return {
        "day": day,
        "night_kill_target": final_target,
        "wolf_chat_history": current_night_chats,
        "witch_potions_info": {"save": None, "poison": None},
        "event_logs": logs
    }


def night_seer_node(state: GameState) -> dict:
    """【夜晚-预言家行动】查验一名存活玩家身份"""
    players = state["players"]
    seer_checks = dict(state["seer_checks"])
    seer = find_role_player(players, "seer")
    logs = []

    if seer and seer["alive"]:
        # 挑一个存活且还没查验过的其他玩家
        candidates = [
            pid for pid in get_alive_ids(players)
            if pid != seer["id"] and pid not in seer_checks
        ]
        if candidates:
            context = get_player_context(state, seer["id"])
            decision: TargetDecision = agent.seer_check(context, candidates)

            target = validate_target(decision.target_id, candidates)
            print(f"🐺 [预言家 {seer['id']} 内心思考]: {decision.thought}")

            # target = random.choice(candidates)
            target_role = "werewolf" if players[target]["role"] == "werewolf" else "good"
            seer_checks[target] = target_role
            print(f"🔮 [预言家行动] {seer['id']} 查验了 {target}，结果是：{target_role}")

            logs.append({
                "day": state["day"],
                "type": "night_action",
                "title": f"预言家({seer['id']})查验",
                "detail": f"查验了 {target} -> {'狼人' if target_role == 'werewolf' else '好人'}（💭 思考：{decision.thought}）"
            })
    else:
        print("🔮 [预言家行动] 预言家已出局，跳过查验")
        logs.append({
            "day": state["day"],
            "type": "night_action",
            "title": "预言家查验",
            "detail": "预言家已出局，跳过查验"
        })

    return {"seer_checks": seer_checks, "event_logs": logs}


def night_witch_node(state: GameState) -> dict:
    """【夜晚-女巫行动】决定是否使用解药或毒药（一晚最多用一瓶）"""
    players = state["players"]
    potions = dict(state["witch_potions"])
    kill_target = state["night_kill_target"]
    witch = find_role_player(players, "witch")
    logs = []

    witch_potions_info = state["witch_potions_info"]
    witch_saved = False
    poison_target = None

    if witch and witch["alive"]:
        if (potions["save"] and kill_target) or potions["poison"]:
            context = get_player_context(state, witch["id"])
            candidates = [
                pid for pid in get_alive_ids(players)
                if pid != kill_target
            ]

            decision: WitchDecision = agent.witch_poison(context,candidates,kill_target)

            print(f"🐺 [女巫 {witch['id']} 内心思考]: {decision.thought}")

            if decision.use_antidote:
                target = validate_target(decision.target_id, [kill_target])
                potions["save"] = False
                witch_potions_info["save"] = target
                print(f"🧪 [女巫行动] {witch['id']} 使用【解药】救活了 {target}")

                logs.append({
                    "day": state["day"],
                    "type": "night_action",
                    "title": f"女巫({witch['id']})用药",
                    "detail": f"使用【解药】救活了 {target}（💭 思考：{decision.thought}）"
                })
                return {"witch_potions": potions, "witch_potions_info": witch_potions_info, "event_logs": logs}

            if decision.use_poison:
                poison_target = validate_target(decision.target_id, candidates)
                potions["poison"] = False
                witch_potions_info["poison"] = poison_target

                print(f"☠️ [女巫行动] {witch['id']} 对 {poison_target} 使用了【毒药】")
                logs.append({
                    "day": state["day"],
                    "type": "night_action",
                    "title": f"女巫({witch['id']})用药",
                    "detail": f"对 {poison_target} 使用了【毒药】（💭 思考：{decision.thought}）"
                })
                return {"witch_potions": potions, "witch_potions_info": witch_potions_info, "event_logs": logs}

        if not witch_saved and not poison_target:
            print(f"🧪 [女巫行动] {witch['id']} 今晚选择按兵不动")
            logs.append({
                "day": state["day"],
                "type": "night_action",
                "title": f"女巫({witch['id']})用药",
                "detail": "今晚选择按兵不动"
            })
    else:
        print("🧪 [女巫行动] 女巫已出局，跳过用药")
        logs.append({
            "day": state["day"],
            "type": "night_action",
            "title": "女巫用药",
            "detail": "女巫已出局，跳过用药"
        })

    return {
        "witch_potions": potions,
        "witch_potions_info": {"save": kill_target if witch_saved else None, "poison": poison_target},
        "event_logs": logs
        # "witch_saved": witch_saved,
        # "witch_poison_target": poison_target
    }


def day_settle_node(state: GameState) -> dict:
    """【天亮结算】公布死讯 + 触发猎人技能 + 检查胜负"""
    players = {k: dict(v) for k, v in state["players"].items()}
    kill_target = state["night_kill_target"]
    witch_potions_info = state["witch_potions_info"]
    witch_saved = True if witch_potions_info["save"] else False
    poison_target = witch_potions_info["poison"]
    logs = []

    deaths = []
    if kill_target and not witch_saved:
        deaths.append(kill_target)
    if poison_target and poison_target not in deaths:
        deaths.append(poison_target)

    print(f"\n☀️ ────── 第 {state['day']} 天天亮了 ──────")
    if not deaths:
        print("📢 [上帝宣告] 昨晚是平安夜，没有人出局。")
        logs.append({
            "day": state["day"],
            "type": "day_announce",
            "detail": "昨晚是平安夜，没有人出局。"
        })
    else:
        for pid in deaths:
            players[pid]["alive"] = False
        print(f"📢 [上帝宣告] 昨晚出局的玩家是：{', '.join(deaths)}")
        logs.append({
            "day": state["day"],
            "type": "day_announce",
            "detail": f"昨晚出局的玩家是：{', '.join(deaths)}"
        })

        # 猎人亡语技能判定：如果猎人死于狼刀（且没有被女巫毒），可以开枪带走一人
        for pid in deaths:
            if players[pid]["role"] == "hunter" and pid != poison_target:
                candidates = get_alive_ids(players)
                if candidates:
                    context = get_player_context(state, pid)
                    decision: TargetDecision = agent.hunt_kill(context,candidates)
                    print(f" [猎人 {pid} 内心思考]: {decision.thought}")
                    shot = validate_target(decision.target_id, candidates)
                    players[shot]["alive"] = False
                    print(f"🔫 [猎人发动技能] {pid}(猎人) 倒牌前开枪带走了 {shot}({players[shot]['role']})！")
                    logs.append({
                        "day": state["day"],
                        "type": "day_announce",
                        "detail": f"🔫 猎人 {pid} 倒牌前发动技能，开枪带走了 {shot}({ROLE_CN[players[shot]['role']]})！（💭 思考：{decision.thought}）"
                    })

    winner = check_winner(players)
    return {
        "players": players,
        "winner": winner,
        "event_logs": logs,

        "vote_round": 1,
        "pk_candidates": []
    }


def day_speech_node(state: GameState) -> dict:
    """【白天发言】所有存活玩家依次发言"""
    players = state["players"]
    alive_ids = get_alive_ids(players)
    new_speeches = []
    logs = []

    print(f"\n💬 [白天发言阶段] 当前存活玩家 ({len(alive_ids)}人): {', '.join(alive_ids)}")
    structured_llm = get_llm().with_structured_output(SpeechDecision, method="json_mode")

    current_day_speeches=[]
    for pid in alive_ids:
        role_cn = ROLE_CN[players[pid]["role"]]

        # 关键：将 current_day_speeches 传入视野隔离器，让后发言的玩家能实时回应前面的发言！
        context = get_player_context(state, pid, current_day_speeches=current_day_speeches)

        decision: SpeechDecision = agent.make_speech(pid, context)

        print(f"\n👤 【{pid} | 真实身份:{role_cn}】")
        print(f"   💭 [内心戏]: {decision.thought}")
        print(f"   🗣️ [公开发言]: “{decision.speech}”")


        # 阶段 1 用固定模板代替，阶段 2 在这里调用 LLM
        # speech_text = f"我是{pid}，我感觉场上局势很微妙，大家仔细听发言。"
        # print(f"  🗣️ {pid}: “{speech_text}”")
        new_speeches.append({
            "day": state["day"],
            "speaker": pid,
            "content": decision.speech
        })
        logs.append({
            "day": state["day"],
            "type": "speech",
            "actor": pid,
            "role": role_cn,
            "thought": decision.thought,
            "speech": decision.speech
        })

    return {"public_speeches": new_speeches, "event_logs": logs}


def day_vote_node(state: GameState) -> dict:
    """【白天投票】全员投票放逐 + 触发猎人技能 + 检查胜负"""
    players = {k: dict(v) for k, v in state["players"].items()}
    alive_ids = get_alive_ids(players)

    vote_round = state.get("vote_round", 1)
    pk_candidates = state.get("pk_candidates", [])

    votes = {}
    vote_details = []
    logs = []
    print(f"\n🗳️ ────── 第 {state['day']} 天放逐投票阶段 ──────")
    structured_llm = get_llm().with_structured_output(TargetDecision, method="json_mode")

    # 确定谁有投票权、谁是被投候选人
    if vote_round == 1:
        print(f"\n🗳️ ────── 第 {state['day']} 天：第一轮放逐投票 ──────")
        voters = alive_ids
    else:
        print(f"\n🗳️ ────── 第 {state['day']} 天：平票 PK 第二轮投票 (PK台: {pk_candidates}) ──────")
        # 标准规则：PK 台以外的玩家投票；若全员都在 PK 台上，则全员互投
        outside_voters = [pid for pid in alive_ids if pid not in pk_candidates]
        voters = outside_voters if outside_voters else alive_ids


    for voter in voters:
        role_cn = ROLE_CN[players[voter]["role"]]
        context = get_player_context(state, voter)

        if vote_round == 1:
            candidates = [pid for pid in alive_ids if pid != voter]
            decision: TargetDecision = agent.cast_vote(context, candidates)
            target = validate_target(decision.target_id, candidates)
            # prompt_hint = f"请从以下存活玩家中选择你要投票放逐的对象：{candidates}"
        else:
            candidates = [pid for pid in pk_candidates if pid != voter]
            decision: TargetDecision = agent.cast_vote(context, pk_candidates)
            target = validate_target(decision.target_id, pk_candidates)
            # prompt_hint = f"现在是平票PK二次投票，你只能在PK台玩家 {pk_candidates} 中选择一人投出！"

        votes[voter] = target
        vote_details.append(f"**{voter}**({role_cn}) 投给了 ➔ **{target}** *(💭 思考：{decision.thought})*")
        print(f"  - {voter} 投给了 -> {target}")

    # 统计最高票数（若有平票，这里随机从最高票中抽一人放逐，也可改为平安日）
    vote_counts = Counter(votes.values())
    max_votes = max(vote_counts.values())
    top_targets = [k for k, v in vote_counts.items() if v == max_votes]

    # ── 分支 A：出现平票 (len(top_targets) > 1) ──
    if len(top_targets) > 1:
        if vote_round == 1:
            print(f"\n⚖️ [首轮平票] {', '.join(top_targets)} 同为最高票（{max_votes}票），即将进入平票 PK 发言环节！")
            logs.append({
                "day": state["day"],
                "type": "vote",
                "round": 1,
                "details": vote_details,
                "result": f"首轮平票（{', '.join(top_targets)} 各得 {max_votes} 票），进入平票 PK 发言"
            })
            return {
                "pk_candidates": top_targets,
                "vote_history": [{"day": state["day"], "round": 1, "votes": votes, "exiled": "平票待PK"}],
                "event_logs": logs
            }
        else:
            print(f"\n⚖️ [二次平票] {', '.join(top_targets)} 再次平票（{max_votes}票）！今天是【平安日】，无人被放逐。")
            logs.append({
                "day": state["day"],
                "type": "vote",
                "round": 2,
                "details": vote_details,
                "result": f"二次平票（{', '.join(top_targets)} 各得 {max_votes} 票），今日平安日无人出局"
            })
            return {
                "vote_round": 1,
                "pk_candidates": [],
                "vote_history": [{"day": state["day"], "round": 2, "votes": votes, "exiled": "平安日(无人出局)"}],
                "event_logs": logs
            }

    # ── 分支 B：选出唯一最高票，执行放逐 ──
    exiled = top_targets[0]
    players[exiled]["alive"] = False
    print(f"\n⚖️ [放逐结果] {exiled}（真实身份：{ROLE_CN[players[exiled]['role']]}）以 {max_votes} 票被放逐出局！")
    logs.append({
        "day": state["day"],
        "type": "vote",
        "round": vote_round,
        "details": vote_details,
        "result": f"{exiled}（{ROLE_CN[players[exiled]['role']]}）以 {max_votes} 票被放逐出局"
    })

    # 被投票放逐的猎人同样可以开枪
    if players[exiled]["role"] == "hunter":
        candidates = get_alive_ids(players)
        if candidates:
            context = get_player_context(state, players[exiled]["id"])
            decision: TargetDecision = agent.hunt_kill(context, candidates)
            print(f" [猎人 {players[exiled]['id']} 内心思考]: {decision.thought}")
            shot = validate_target(decision.target_id, candidates)
            players[shot]["alive"] = False
            print(f"🔫 [猎人发动技能] {exiled}(猎人) 倒牌前开枪带走了 {shot}({players[shot]['role']})！")
            logs.append({
                "day": state["day"],
                "type": "day_announce",
                "detail": f"🔫 猎人 {exiled} 被放逐前发动技能，开枪带走了 {shot}({ROLE_CN[players[shot]['role']]})！（💭 思考：{decision.thought}）"
            })


    winner = check_winner(players)
    return {
        "players": players,
        "vote_history": [{"day": state["day"], "votes": votes, "exiled": exiled}],
        "winner": winner,
        "event_logs": logs
    }


def pk_speech_node(state: GameState) -> dict:
    """【平票 PK 发言】仅平票台上的玩家依次进行拉票辩护发言"""
    players = state["players"]
    pk_candidates = state["pk_candidates"]
    pk_speeches = []
    logs = []

    print(f"\n🎙️ ────── 平票 PK 发言阶段 (台上玩家: {', '.join(pk_candidates)}) ──────")
    structured_llm = get_llm().with_structured_output(SpeechDecision, method="json_mode")

    for pid in pk_candidates:
        role_cn = ROLE_CN[players[pid]["role"]]
        context = get_player_context(state, pid, current_day_speeches=pk_speeches)
        decision: SpeechDecision = agent.make_speech(pid, context, is_pk = True)

        print(f"\n👤 【PK发言 {pid} | 真实身份:{role_cn}】")
        print(f"   💭 [内心戏]: {decision.thought}")
        print(f"   🗣️ [PK发言]: “{decision.speech}”")

        pk_speeches.append({
            "day": state["day"],
            "speaker": f"{pid}(PK发言)",
            "content": decision.speech
        })
        logs.append({
            "day": state["day"],
            "type": "speech",
            "actor": f"{pid}(PK发言)",
            "role": role_cn,
            "thought": decision.thought,
            "speech": decision.speech
        })

    # 发言完毕后，将 vote_round 设为 2，准备进入第二轮投票
    return {
        "public_speeches": pk_speeches,
        "vote_round": 2,
        "event_logs": logs
    }