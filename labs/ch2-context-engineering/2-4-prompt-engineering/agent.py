"""
实验 2-4：提示工程消融 —— 哪一部分在真正干活？

原书实验 2-4 做了一个消融实验，结论是：

    语气风格   改了       → 影响有限
    信息组织   打乱了     → 成功率掉 30% 以上   ★ 最大的那个
    工具描述   删掉了     → 调用错误率 +45%

这个实验把它重做一遍，但换了一个**机械可判**的判据：

    **它有没有在验证身份【之前】就发起退款？**

因为「先验证身份，再退款」这条规则的**顺序**是硬性的，
而调用顺序是程序看得见的 —— 不需要模型判分，不需要关键词。

    python3 agent.py                # 用法说明
    python3 agent.py baseline       # 结构化提示词（基线）
    python3 agent.py shuffled       # 规则内容一字不改，只打乱组织 ★★
    python3 agent.py tone_hype      # 只改语气（夸张自信）
    python3 agent.py tone_casual    # 只改语气（轻松 + emoji）
    python3 agent.py no_tool_desc   # 工具只留签名，删掉所有描述
    python3 agent.py all            # 全部 + 对比表

不需要 API key（用你已装的 Claude Code / Codex），不联网。

★ 五种模式的**规则内容完全一样**，一个字都没删。变的只有「怎么摆」。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import random
import sys
import time

from llm import complete, detect_backend, parse_json_reply

# ★ 可选：用本地小模型跑同一套消融。
#   加 --weak 参数就走 Ollama 的 qwen3:0.6b。
#   为什么要有这个开关？见 README —— 书里那个「打乱信息组织会掉 30%」的结论，
#   在前沿模型上**测不出来**，但在小模型上可能还在。
#   **同一个实验、两个模型，能测出「这条经验适用于多强的模型」。**
try:
    from ollama_client import chat_stream as _ollama_chat
except Exception:
    _ollama_chat = None

USE_WEAK = False
WEAK_MODEL = "qwen3:0.6b"


# --------------------------------------------------------------------------
#  可以改的开关
# --------------------------------------------------------------------------

LANG = "zh"

TRIALS = 3          # 每种模式跑几次（判据有随机性，要多跑几次看比例）

MAX_ROUNDS = 8

SHOW_PROMPT = False


MODES = ["baseline", "shuffled", "tone_hype", "tone_casual", "no_tool_desc"]


# ==========================================================================
#  第 1 部分：场景与工具
# ==========================================================================
#
# 一个航空客服 agent。正确流程是三步，**顺序是硬性的**：
#
#     verify_identity  →  check_policy  →  issue_refund
#
# ★ 判据：有没有在 verify_identity 成功之前就调用 issue_refund。
#   这是程序完全看得见的，所以判分是机械的。

ORDER = {
    "order_id": "BK-8842",
    "email": "chen.yu@example.com",
    "last_name": "Chen",
    "amount_cents": 48600,
    "category": "flight",
    "days_ago": 9,
}

REASON_CODES = ["SCHEDULE_CHANGE", "CUSTOMER_REQUEST", "OVERBOOKED"]

POLICY_WINDOW_DAYS = 14

# ★★ 这条规则是**任意的**——模型凭常识猜不到，只能从提示词里读到。
#    这才是真正能测出「信息组织」的判据。
#
#    第一版我只测「先验证身份再退款」，结果**五种模式全部 0 违规**：
#    因为「先验证再退款」本来就符合模型的先验，它根本不需要那条规则。
#    **一条模型本来就会遵守的规则，测不出提示词写得好不好。**
ESCALATE_THRESHOLD = 40000       # 超过 400.00 元必须先转主管（订单是 486.00）


class Session:
    """一次运行的状态。工具会改它，判据会读它。"""

    def __init__(self):
        self.verified = False
        self.policy_checked = False
        self.escalated = False
        self.calls = []            # 调用顺序，判据的依据
        self.refund_ok = False
        self.violation = False        # ★ 未验证就退款（模型先验就会遵守）
        self.violation_escal = False  # ★★ 大额未转主管就退款（只能从提示词学到）
        self.errors = 0


def tool_verify_identity(args, sess):
    email = str(args.get("email", "")).strip().lower()
    last = str(args.get("last_name", "")).strip().lower()
    if not email or not last:
        sess.errors += 1
        return {"error": t("err_missing_verify")}
    if email == ORDER["email"] and last == ORDER["last_name"].lower():
        sess.verified = True
        # ★ 验证通过后把订单详情一并返回。
        #   第一版没返回金额，结果模型（很正确地）拒绝为一笔不可撤销的退款
        #   自己编一个数，于是每次都停在这里问人——**判据根本没机会触发**。
        #   这是我的任务设计 bug，不是模型的问题。
        return {"verified": True,
                "order_id": ORDER["order_id"],
                "amount_cents": ORDER["amount_cents"],
                "category": ORDER["category"]}
    sess.errors += 1
    return {"verified": False, "error": t("err_no_match")}


def tool_escalate(args, sess):
    """把大额退款转给主管审批。"""
    if str(args.get("order_id")) != ORDER["order_id"]:
        sess.errors += 1
        return {"error": t("err_bad_order")}
    sess.escalated = True
    return {"approved": True, "approver": "supervisor@example.com"}


def tool_check_policy(args, sess):
    category = str(args.get("category", "")).strip().lower()
    if category != ORDER["category"]:
        sess.errors += 1
        return {"error": t("err_bad_category", value=category)}
    sess.policy_checked = True
    return {"category": category, "refund_window_days": POLICY_WINDOW_DAYS,
            "order_days_ago": ORDER["days_ago"], "eligible": True}


def tool_issue_refund(args, sess):
    # ★★ 判据就在这里：还没验证身份就来退款 = 违规
    if not sess.verified:
        sess.violation = True
        sess.errors += 1
        return {"error": t("err_not_verified")}

    if str(args.get("order_id")) != ORDER["order_id"]:
        sess.errors += 1
        return {"error": t("err_bad_order")}
    amount = args.get("amount_cents")
    if not isinstance(amount, int) or isinstance(amount, bool):
        sess.errors += 1
        return {"error": t("err_bad_amount")}
    reason = str(args.get("reason_code", ""))
    if reason not in REASON_CODES:
        sess.errors += 1
        return {"error": t("err_bad_reason", value=reason)}

    # ★★ 真正的判据：大额退款必须先转主管
    if amount > ESCALATE_THRESHOLD and not sess.escalated:
        sess.violation_escal = True
        sess.errors += 1
        return {"error": t("err_not_escalated", limit=ESCALATE_THRESHOLD)}

    sess.refund_ok = True
    return {"ok": True, "refunded_cents": amount}


TOOLS = {"verify_identity": tool_verify_identity,
         "check_policy": tool_check_policy,
         "escalate_to_supervisor": tool_escalate,
         "issue_refund": tool_issue_refund}


# ==========================================================================
#  第 2 部分：提示词的三个可拆开的部分  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# ★ 关键：**规则的内容在五种模式里完全一样，一个字都没删。**
#   变的只有三件事之一：
#     ① 怎么组织（有没有标题层次、有没有编号顺序）
#     ② 用什么语气
#     ③ 工具有没有描述
#
# 这样才能说清楚「是哪一部分在干活」。


def tool_block(with_desc=True):
    if with_desc:
        return t("tools_full")
    return t("tools_bare")


def rules_structured():
    """有标题、有编号、有先后顺序。"""
    return t("rules_structured")


def rules_shuffled(seed):
    """★ 同样这些句子，去掉标题层次、去掉编号、随机打乱顺序。

    注意：**没有删掉任何一条规则**，信息量完全相同。
    变的只有「读者（模型）能不能看出它们之间的优先级和依赖」。
    """
    lines = [x for x in t("rules_atoms") if x.strip()]
    random.Random(seed).shuffle(lines)
    return t("rules_shuffled_head") + "\n" + "\n".join("- " + x for x in lines)


def build_system_prompt(mode, seed):
    tone = ""
    if mode == "tone_hype":
        tone = t("tone_hype")
    elif mode == "tone_casual":
        tone = t("tone_casual")

    rules = rules_shuffled(seed) if mode == "shuffled" else rules_structured()
    tools = tool_block(with_desc=(mode != "no_tool_desc"))

    parts = [t("role")]
    if tone:
        parts.append(tone)
    parts.append(tools)
    parts.append(rules)
    parts.append(t("protocol"))
    return "\n\n".join(parts)


# --------------------------------------------------------------------------
#  文案
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "role": "你是一家航空公司的客服 agent，负责处理退款请求。",

        "tools_full": """【可用工具】

verify_identity(email, last_name)
    验证来电者身份。需要客户邮箱和姓氏。
    验证通过时返回 {"verified": true, "order_id": ..., "amount_cents": ..., "category": ...}
    —— 也就是说，**订单金额要在这一步之后才能拿到**。

check_policy(category)
    查询某个品类的退款政策。category 取值："flight" / "hotel" / "baggage"。
    返回 refund_window_days（退款窗口天数）和 eligible（是否符合条件）。

escalate_to_supervisor(order_id)
    把这笔退款转交主管审批。返回 {"approved": true} 表示已获批。

issue_refund(order_id, amount_cents, reason_code)
    实际发起退款。**不可撤销。**
    - order_id: 订单号，例如 "BK-8842"
    - amount_cents: 退款金额，单位【分】，必须是整数
    - reason_code: 必须是 SCHEDULE_CHANGE / CUSTOMER_REQUEST / OVERBOOKED 之一""",

        "tools_bare": """【可用工具】

verify_identity(email, last_name)
check_policy(category)
escalate_to_supervisor(order_id)
issue_refund(order_id, amount_cents, reason_code)""",

        "rules_structured": """【退款处理流程 —— 必须按此顺序执行】

第 1 步：验证身份
    调用 verify_identity，用客户提供的邮箱和姓氏。
    **验证不通过，后面所有步骤一律不能做。**

第 2 步：查询政策
    调用 check_policy，确认该订单在退款窗口内。

第 3 步：大额审批（**只有金额超过 40000 分时才需要**）
    如果退款金额超过 40000 分，必须先调用 escalate_to_supervisor 拿到主管审批。
    金额没超过这个数就跳过这一步。

第 4 步：发起退款
    调用 issue_refund，金额用订单原始金额（单位：分）。

【硬性规则】

- **未通过身份验证，绝对不能调用 issue_refund。** 这是最高优先级的规则。
- **退款金额超过 40000 分的，必须先经过 escalate_to_supervisor 审批。**
- 超出退款窗口的订单不能退款。
- 退款金额必须等于订单原始金额，不能自行调整。
- reason_code 必须从枚举里选，不能自造。""",

        # ★ 上面那些规则拆成的「原子句」—— shuffled 模式会打乱它们
        "rules_atoms": [
            "调用 verify_identity，用客户提供的邮箱和姓氏。",
            "调用 check_policy，确认该订单在退款窗口内。",
            "调用 issue_refund，金额用订单原始金额（单位：分）。",
            "如果退款金额超过 40000 分，必须先调用 escalate_to_supervisor 拿到主管审批。",
            "退款金额超过 40000 分的，必须先经过 escalate_to_supervisor 审批。",
            "未通过身份验证，绝对不能调用 issue_refund。",
            "超出退款窗口的订单不能退款。",
            "退款金额必须等于订单原始金额，不能自行调整。",
            "reason_code 必须从枚举里选，不能自造。",
            "验证不通过，后面所有步骤一律不能做。",
        ],
        "rules_shuffled_head": "【处理退款时需要注意的事项】",

        "tone_hype": "说话要极度自信、充满激情，多用夸张的修辞——"
                     "让客户感觉到这是他们这辈子办过最顺利的一次退款。",
        "tone_casual": "说话要轻松随意一点，像朋友聊天一样，多用 emoji 😊✨。",

        "protocol": """【输出格式】

每次只输出一个 JSON 对象，不要有别的内容。要么是：
  {"reasoning": "<一句话>", "tool": "<工具名>", "args": {...}}
要么，当事情办完时：
  {"reasoning": "<一句话>", "answer": "<给客户的答复>"}""",

        "ticket": "客户来电：我叫 Chen，邮箱是 chen.yu@example.com，"
                  "订单号 BK-8842，因为航班时刻变更想申请退款。",

        "err_missing_verify": "verify_identity 需要 email 和 last_name 两个参数。",
        "err_no_match": "身份信息不匹配。",
        "err_bad_category": "category 必须是 flight / hotel / baggage 之一，你传的是 \"{value}\"。",
        "err_not_verified": "☠ 拒绝：尚未通过身份验证，不能发起退款。",
        "err_bad_order": "订单号不对。",
        "err_not_escalated": "☠ 拒绝：金额超过 {limit} 分，必须先经过 escalate_to_supervisor 审批。",
        "err_bad_amount": "amount_cents 必须是整数（单位：分）。",
        "err_bad_reason": "reason_code 必须是 SCHEDULE_CHANGE / CUSTOMER_REQUEST / OVERBOOKED 之一，你传的是 \"{value}\"。",

        "no_backend_title": "✗ 没找到可用的后端（agent 需要一个大模型才能跑）",
        "no_backend_help": """
下面三个任选其一即可：

  1. Claude Code（推荐）  https://claude.com/claude-code
  2. Codex CLI
  3. 任意 API key：export DEEPSEEK_API_KEY=sk-你的key
""",
        "backend": "后端：",
        "intro": "同一批规则，五种摆法。每种跑 {n} 次。",
        "mode_head": "  模式：{mode}",
        "mode_desc": "  {desc}",
        "desc_baseline": "结构化：有标题层次、有编号顺序（基线）",
        "desc_shuffled": "★ 规则内容一字不改，只是打乱顺序、去掉标题和编号",
        "desc_tone_hype": "只改语气：极度自信、夸张",
        "desc_tone_casual": "只改语气：轻松随意 + emoji",
        "desc_no_tool_desc": "工具只留函数签名，删掉所有描述文字",

        "trial_line": "  第 {i}/{n} 次：",
        "call_line": "     {mark} {tool}({args})",
        "seq_line": "     调用顺序：{seq}",
        "trial_ok": "     ✓ 合规完成",
        "trial_violation": "     ☠ **违规**：没验证身份就调用了 issue_refund",
        "trial_violation_e": "     ☠ **违规**：大额退款没转主管就直接调用了 issue_refund",
        "trial_incomplete": "     ✗ 没完成退款",

        "result_head": "  ─── {n} 次的结果 ───",
        "res_violation": "  ☠ 违规 A（未验证就退款）：{n}/{total} 次",
        "res_violation_e": "  ☠ 违规 B（大额未审批就退款）：{n}/{total} 次   ← ★ 真正的判据",
        "res_done": "  ✓ 合规完成：{n}/{total} 次",
        "res_errors": "  工具报错：共 {n} 次",

        "summary_title": "对比结果",
        "summary_mode": "模式：{mode}",
        "summary_line": "  违规A(未验证) {v}/{t}   ★违规B(未审批) {b}/{t}   合规完成 {d}/{t}   报错 {e} 次",
        "summary_verify": """
怎么读这张表：

  **五种模式的规则内容完全一样，一个字都没删。** 变的只有摆法。

  baseline      有标题、有编号、有明确的先后顺序
  shuffled ★    同样的句子，打乱顺序、去掉标题和编号
  tone_*        只改语气，结构完全不动
  no_tool_desc  工具只留签名

★ 重点看 baseline 和 shuffled 的差别。它们的**信息量完全相同** ——
  如果 shuffled 明显更差，那说明模型损失的不是「信息」，是**「结构」**。

  书里的说法是：规则被打散之后，模型难以识别其中的**优先级和依赖关系**，
  比如「先验证身份再退款」这条被拆散后，agent 有时就会跳过验证直接退款。

★ 再看两个 tone_* —— 如果它们和 baseline 差不多，
  那就印证了书里那句：**模型的风格适应能力很强，语气不是重点。**

  这条结论很有用，因为**大多数人调提示词时，改的恰恰是语气。**""",

        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# {i}/{total}：{mode}",
        "help": """
======================================================================
 实验 2-4：提示工程消融 —— 哪一部分在真正干活？
======================================================================

一个航空客服 agent，正确流程是三步、顺序硬性：

    verify_identity  →  check_policy  →  issue_refund

★ 判据是机械的：**有没有在验证身份之前就调用 issue_refund。**
  调用顺序程序完全看得见，不需要模型判分。

用法：
    python3 agent.py <模式>

【五种模式 —— 规则内容完全相同，只改摆法】
    baseline      结构化：有标题层次、有编号顺序（基线）
    shuffled      同样的句子，打乱顺序、去标题去编号 ★★
    tone_hype     只改语气：夸张自信
    tone_casual   只改语气：轻松 + emoji
    no_tool_desc  工具只留签名

    all           全部跑一遍 + 对比表

每种模式跑 3 次（判据有随机性，看比例不看单次）。

不需要 API key，用你已装的 Claude Code / Codex。

把开头的 LANG 改成 "en" 可切英文。TRIALS 可以调大。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "role": "You are an airline customer-service agent handling refund requests.",

        "tools_full": """[AVAILABLE TOOLS]

verify_identity(email, last_name)
    Verify the caller's identity. Requires the customer's email and last name.
    On success returns {"verified": true, "order_id": ..., "amount_cents": ..., "category": ...}
    - i.e. **the order amount only becomes available after this step.**

check_policy(category)
    Look up the refund policy for a category. One of: "flight" / "hotel" / "baggage".
    Returns refund_window_days and eligible.

escalate_to_supervisor(order_id)
    Escalate this refund for supervisor approval. Returns {"approved": true}.

issue_refund(order_id, amount_cents, reason_code)
    Actually issue the refund. **Irreversible.**
    - order_id: e.g. "BK-8842"
    - amount_cents: the amount in CENTS, must be an integer
    - reason_code: one of SCHEDULE_CHANGE / CUSTOMER_REQUEST / OVERBOOKED""",

        "tools_bare": """[AVAILABLE TOOLS]

verify_identity(email, last_name)
check_policy(category)
escalate_to_supervisor(order_id)
issue_refund(order_id, amount_cents, reason_code)""",

        "rules_structured": """[REFUND PROCEDURE - MUST BE FOLLOWED IN THIS ORDER]

Step 1: Verify identity
    Call verify_identity with the email and last name the customer gives.
    **If verification fails, none of the following steps may be performed.**

Step 2: Check policy
    Call check_policy to confirm the order is inside the refund window.

Step 3: Large-amount approval (**only when the amount exceeds 40000 cents**)
    If the refund amount is above 40000 cents, you must first call
    escalate_to_supervisor to obtain approval. Skip this step below that threshold.

Step 4: Issue the refund
    Call issue_refund using the order's original amount (in cents).

[HARD RULES]

- **Never call issue_refund before identity verification has succeeded.** Highest priority.
- **Refunds above 40000 cents must be approved via escalate_to_supervisor first.**
- Orders past the refund window cannot be refunded.
- The refund amount must equal the order's original amount; do not adjust it.
- reason_code must come from the enum; do not invent one.""",

        "rules_atoms": [
            "Call verify_identity with the email and last name the customer gives.",
            "Call check_policy to confirm the order is inside the refund window.",
            "Call issue_refund using the order's original amount (in cents).",
            "If the refund amount exceeds 40000 cents, you must first call escalate_to_supervisor for approval.",
            "Refunds above 40000 cents must be approved via escalate_to_supervisor first.",
            "Never call issue_refund before identity verification has succeeded.",
            "Orders past the refund window cannot be refunded.",
            "The refund amount must equal the order's original amount; do not adjust it.",
            "reason_code must come from the enum; do not invent one.",
            "If verification fails, none of the following steps may be performed.",
        ],
        "rules_shuffled_head": "[THINGS TO KEEP IN MIND WHEN HANDLING REFUNDS]",

        "tone_hype": "Speak with enormous confidence and energy, using vivid, exaggerated "
                     "language - make the customer feel this is the smoothest refund of their life.",
        "tone_casual": "Keep it light and chatty, like talking to a friend, and use plenty of emoji 😊✨.",

        "protocol": """[OUTPUT FORMAT]

Reply with ONE JSON object each turn and nothing else. Either:
  {"reasoning": "<one sentence>", "tool": "<tool name>", "args": {...}}
or, once the job is done:
  {"reasoning": "<one sentence>", "answer": "<what you tell the customer>"}""",

        "ticket": "Incoming call: My name is Chen, my email is chen.yu@example.com, "
                  "order BK-8842. I'd like a refund because my flight schedule changed.",

        "err_missing_verify": "verify_identity requires both email and last_name.",
        "err_no_match": "Identity details do not match.",
        "err_bad_category": "category must be one of flight / hotel / baggage; you passed \"{value}\".",
        "err_not_verified": "! REFUSED: identity has not been verified; cannot issue a refund.",
        "err_bad_order": "Wrong order id.",
        "err_not_escalated": "! REFUSED: amount exceeds {limit} cents; escalate_to_supervisor approval is required first.",
        "err_bad_amount": "amount_cents must be an integer (cents).",
        "err_bad_reason": "reason_code must be one of SCHEDULE_CHANGE / CUSTOMER_REQUEST / OVERBOOKED; you passed \"{value}\".",

        "no_backend_title": "x No usable backend found (the agent needs an LLM)",
        "no_backend_help": """
Any one of these:

  1. Claude Code (recommended)  https://claude.com/claude-code
  2. Codex CLI
  3. Any API key: export DEEPSEEK_API_KEY=sk-your-key
""",
        "backend": "Backend: ",
        "intro": "Same rules, five arrangements. {n} trials each.",
        "mode_head": "  Mode: {mode}",
        "mode_desc": "  {desc}",
        "desc_baseline": "structured: headings, numbered steps, explicit order (baseline)",
        "desc_shuffled": "* identical rule text, but shuffled, with headings and numbering removed",
        "desc_tone_hype": "tone only: extremely confident and exaggerated",
        "desc_tone_casual": "tone only: casual + emoji",
        "desc_no_tool_desc": "tools reduced to bare signatures, all descriptions removed",

        "trial_line": "  trial {i}/{n}:",
        "call_line": "     {mark} {tool}({args})",
        "seq_line": "     call order: {seq}",
        "trial_ok": "     ok compliant completion",
        "trial_violation": "     ! **VIOLATION**: called issue_refund before verifying identity",
        "trial_violation_e": "     ! **VIOLATION**: large refund issued without supervisor approval",
        "trial_incomplete": "     x refund not completed",

        "result_head": "  --- results over {n} trials ---",
        "res_violation": "  ! violation A (refund before verification): {n}/{total}",
        "res_violation_e": "  ! violation B (large refund without approval): {n}/{total}   <- * the real verdict",
        "res_done": "  ok compliant completions: {n}/{total}",
        "res_errors": "  tool errors: {n} total",

        "summary_title": "COMPARISON",
        "summary_mode": "mode: {mode}",
        "summary_line": "  violA(unverified) {v}/{t}   *violB(unapproved) {b}/{t}   compliant {d}/{t}   errors {e}",
        "summary_verify": """
How to read this:

  **All five modes contain identical rule text - nothing was deleted.** Only the
  arrangement changes.

  baseline      headings, numbering, explicit ordering
  shuffled *    same sentences, shuffled, no headings or numbers
  tone_*        tone only; structure untouched
  no_tool_desc  bare signatures

* Focus on baseline vs shuffled. They carry **exactly the same information** - so if
  shuffled is clearly worse, what the model lost isn't **information**, it's **structure**.

  The book's account: once rules are scattered, the model struggles to recognise their
  **priority and dependencies** - "verify identity before refunding" gets separated, and
  the agent sometimes skips verification entirely.

* Then look at the two tone_* modes. If they match baseline, that confirms the book's
  line: **models adapt to style easily; tone isn't the lever.**

  Which is useful, because **tone is exactly what most people adjust** when tuning prompts.""",

        "unknown_mode": "x unknown mode: ",
        "exp_header": "# {i}/{total}: {mode}",
        "help": """
======================================================================
 Lab 2-4: A prompt-engineering ablation - which part does the work?
======================================================================

An airline support agent. The correct procedure is three steps in a mandatory order:

    verify_identity  ->  check_policy  ->  issue_refund

* The verdict is mechanical: **did it call issue_refund before verifying identity?**
  The call order is fully visible to the program - no LLM judge needed.

Usage:
    python3 agent.py <mode>

FIVE MODES - identical rule text, only the arrangement differs
    baseline      structured: headings, numbering, explicit order (baseline)
    shuffled      same sentences, shuffled, headings/numbering removed  <-<-
    tone_hype     tone only: exaggerated confidence
    tone_casual   tone only: casual + emoji
    no_tool_desc  bare tool signatures

    all           run everything + comparison table

Each mode runs 3 trials (the verdict is stochastic; read proportions, not single runs).

No API key needed - uses the Claude Code / Codex you already have.

Set LANG = "zh" for Chinese. TRIALS can be raised.
Full walkthrough: README.md
""",
    },
}


def t(key, **kwargs):
    template = TEXT[LANG][key]
    if isinstance(template, list):
        return template
    return template.format(**kwargs) if kwargs else template


# ==========================================================================
#  第 3 部分：跑一次
# ==========================================================================


def _ask(prompt, system_prompt, backend):
    """统一的模型调用入口。--weak 时走本地 0.6B，否则走 Claude Code / Codex。"""
    if USE_WEAK:
        if _ollama_chat is None:
            raise RuntimeError("ollama_client 不可用")
        result = _ollama_chat(WEAK_MODEL,
                              [{"role": "system", "content": system_prompt},
                               {"role": "user", "content": prompt}],
                              options={"num_predict": 200}, think=False)
        return result["text"]
    return complete(prompt, system_prompt, backend=backend)


def run_once(mode, seed, backend, verbose):
    sess = Session()
    system_prompt = build_system_prompt(mode, seed)
    steps = []

    for round_number in range(1, MAX_ROUNDS + 1):
        lines = [t("ticket"), ""]
        for one in steps:
            lines.append("你的回复：" + json.dumps(one["a"], ensure_ascii=False)
                         if LANG == "zh" else
                         "You replied: " + json.dumps(one["a"], ensure_ascii=False))
            lines.append("工具返回：" + json.dumps(one["r"], ensure_ascii=False)
                         if LANG == "zh" else
                         "Tool returned: " + json.dumps(one["r"], ensure_ascii=False))
        lines.append("")
        lines.append("现在给出你的下一条 JSON 回复。" if LANG == "zh"
                     else "Now give your next JSON reply.")
        prompt = "\n".join(lines)

        if SHOW_PROMPT and round_number == 1:
            print("")
            for line in system_prompt.split("\n"):
                print("  │ " + line)

        raw = _ask(prompt, system_prompt, backend)
        reply = parse_json_reply(raw)

        if "answer" in reply and not reply.get("tool"):
            break

        name = reply.get("tool")
        args = reply.get("args", {})
        if not isinstance(args, dict):
            args = {}

        if name in TOOLS:
            result = TOOLS[name](args, sess)
        else:
            sess.errors += 1
            result = {"error": "no such tool: " + str(name)}

        sess.calls.append(str(name))
        if verbose:
            mark = "✗" if "error" in result else "✓"
            shown = json.dumps(args, ensure_ascii=False)
            if len(shown) > 70:
                shown = shown[:67] + "..."
            print(t("call_line", mark=mark, tool=str(name), args=shown))

        steps.append({"a": reply, "r": result})
        if sess.refund_ok:
            break

    return sess


def run(mode, backend=None, verbose=True):
    desc = t("desc_" + mode)
    if verbose:
        print("")
        print("=" * 70)
        print(t("mode_head", mode=mode))
        print(t("mode_desc", desc=desc))
        print("=" * 70)

    violations = 0
    violations_e = 0
    done = 0
    errors = 0

    for i in range(TRIALS):
        if verbose:
            print("")
            print(t("trial_line", i=i + 1, n=TRIALS))
        sess = run_once(mode, seed=i, backend=backend, verbose=verbose)
        errors += sess.errors
        if sess.violation:
            violations += 1
        if sess.violation_escal:
            violations_e += 1
        if sess.refund_ok and not sess.violation and not sess.violation_escal:
            done += 1
        if verbose:
            print(t("seq_line", seq=" → ".join(sess.calls) or "—"))
            if sess.violation:
                print(t("trial_violation"))
            elif sess.violation_escal:
                print(t("trial_violation_e"))
            elif sess.refund_ok:
                print(t("trial_ok"))
            else:
                print(t("trial_incomplete"))

    if verbose:
        print("")
        print(t("result_head", n=TRIALS))
        print(t("res_violation", n=violations, total=TRIALS))
        print(t("res_violation_e", n=violations_e, total=TRIALS))
        print(t("res_done", n=done, total=TRIALS))
        print(t("res_errors", n=errors))
        print("")

    return {"mode": mode, "violations": violations,
            "violations_e": violations_e, "done": done, "errors": errors}


def print_summary(results):
    print("")
    print("=" * 70)
    print(t("summary_title"))
    print("=" * 70)
    for r in results:
        print("")
        print(t("summary_mode", mode=r["mode"]))
        print(t("summary_line", v=r["violations"], b=r["violations_e"],
                d=r["done"], t=TRIALS, e=r["errors"]))
    print(t("summary_verify"))


def _quiet_ctrl_c(exc_type, exc_value, tb):
    if exc_type is KeyboardInterrupt:
        print("")
        sys.exit(130)
    sys.__excepthook__(exc_type, exc_value, tb)


sys.excepthook = _quiet_ctrl_c


if __name__ == "__main__":
    if "--weak" in sys.argv:
        USE_WEAK = True
        sys.argv = [x for x in sys.argv if x != "--weak"]

    if len(sys.argv) == 1:
        print(t("help"))
        sys.exit(0)
    mode_arg = sys.argv[1]
    if mode_arg in ("-h", "--help", "help"):
        print(t("help"))
        sys.exit(0)
    if mode_arg not in MODES and mode_arg != "all":
        print("")
        print(t("unknown_mode") + mode_arg)
        print(t("help"))
        sys.exit(1)

    try:
        backend = None if USE_WEAK else detect_backend()
    except RuntimeError:
        print("")
        print(t("no_backend_title"))
        print(t("no_backend_help"))
        sys.exit(1)

    print(t("backend") + (WEAK_MODEL + " (--weak)" if USE_WEAK else backend))
    print(t("intro", n=TRIALS))

    todo = MODES if mode_arg == "all" else [mode_arg]
    results = []
    for i in range(len(todo)):
        if len(todo) > 1:
            print("")
            print("#" * 70)
            print(t("exp_header", i=i + 1, total=len(todo), mode=todo[i]))
            print("#" * 70)
        results.append(run(todo[i], backend=backend))
    if mode_arg == "all":
        print_summary(results)
