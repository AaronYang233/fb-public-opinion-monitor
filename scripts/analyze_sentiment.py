#!/usr/bin/env python3
"""
Facebook 舆情分析脚本（双语版）
支持中英文关键词，自动情感判断、问题分类、严重程度评估

用法：
  python3 analyze_sentiment.py                    # 交互模式
  python3 analyze_sentiment.py "文本内容"          # 单条分析
  python3 analyze_sentiment.py --file posts.json   # 批量文件
"""

import re
import sys
import json
from typing import Dict, List, Tuple

# ============================================================
# 中英双语关键词库（正则模式，支持大小写）
# ============================================================

STRONG_NEGATIVE_PATTERNS = [
    # 中文强负面
    "退货", "退款", "投诉", "举报", "欺诈", "骗子", "假货", "劣质",
    "质量差", "做工差", "货不对板", "严重", "致命", "完全失败",
    "垃圾", "废物", "毫无用处", "欺骗消费者", "三无产品",
    "有毒", "危险", "安全隐患", "爆炸", "起火", "过热",
    # 英文强负面（正则）
    r"\breturn\b.*\b(fraud|scam|ripoff|lawsuit)\b",
    r"\b(fraud|scam|ripoff)\b",
    r"\b(lawsuit|legal\s*action|solicitor)\b",
    r"\bterrible\s*(quality|product|experience)\b",
    r"\bworst\s*car\b",
    r"\bfire\b.*\b(battery|car|charge)\b",
    r"\bexplod\w*\b",
    r"\bpoison\w*\b|\btoxic\b.*\bsmell\b",
    r"\bpermanent\s*damage\b",
    r"\bcan'?t\s*(drive|use|charge)\b.*\b(broken|dead)\b",
    r"\bcompletely\s*(broken|useless)\b",
    r"\b(illegal|dangerous)\s*(product|car)\b",
    r"\bwill\s*never\s*buy\b",
    r"\bbuyers\s*beware\b",
]

NEGATIVE_PATTERNS = [
    # 中文负面
    "不满", "失望", "差", "糟糕", "难用", "不好", "问题", "故障",
    "损坏", "有瑕疵", "划痕", "变形", "褪色", "异味", "不舒服",
    "延迟", "很久没到", "太慢了", "客服态度差", "推诿",
    "不处理", "没人管", "希望改进", "需要加强",
    # 英文负面（正则）
    r"\b(disappointed|unsatisfied|unhappy|angry)\b",
    r"\b(problem|issue|trouble)\b",
    r"\b(broke|broken|not\s*work)\b",
    r"\b(fault|faulty|defect)\b",
    r"\b(complaint|complain)\b",
    r"\bnot\s*(good|great|happy|satisfied)\b",
    r"\b(annoying|frustrat\w*)\b",
    r"\b(recall|service\s*center|dealership)\b",
    r"\bdealer\s*(didn'?t|won'?t|can'?t)\b",
    r"\bno\s*(solution|fix|answer|help)\b",
    r"\bwaiting\s*(for|ago)\b",
    r"\bslow\s*(service|response|reply)\b",
    r"\bpoor\s*(quality|service)\b",
    r"\bdoesn'?t\s*(work|function|charge)\b",
    r"\bcan'?t\s*(use|drive|open|start)\b",
    r"\b(concern|worried|concerned)\b",
    r"\bunnerv\w*\b",
    r"\balarm\b.*\b(false|problem|issue)\b",
    r"\bfalse\s*alarm\b",
    r"\b(won|will).*not.*work\b",
]

POSITIVE_PATTERNS = [
    # 中文正面
    "满意", "很好", "优秀", "超值", "推荐", "喜欢", "实用", "物美价廉",
    "性价比高", "客服好", "服务周到", "解决问题", "响应快",
    "好用", "方便", "漂亮", "好看", "正品",
    # 英文正面（正则）
    r"\b(love[sd]?|liked|great|excellent|amazing|awesome)\b",
    r"\b(recommend|recommended)\b",
    r"\b(happy|satisfied|pleased|delighted)\b",
    r"\b(pleasantly?\s*surprised)\b",
    r"\b(best|good|fair)\s*(value|price|deal)\b",
    r"\bwell\s*(built|designed|made)\b",
    r"\bsmooth\s*(drive|ride)\b",
    r"\bcomfortable\s*(drive|seat|car)\b",
    r"\breal\s*world\s*range\b",
    r"\bbetter\s*than\s*expected\b",
    r"\bno\s*(issue|problem|complaint)\b.*\bso\s*far\b",
    r"\bhappy\s*(with|about)\b",
    r"\bworth\s*(every|the)\s*penny\b",
    r"\b(good|great)\s*(experience|dealership)\b",
    r"\b(quick|fast)\s*(service|response)\b",
    r"\bexceed\w*\s*(expectation)\b",
]

QUALITY_PATTERNS = [
    "破损", "瑕疵", "异味", "褪色", "变形", "材质差", "做工粗糙", "假货",
    r"\b(quality|build)\s*(issue|problem|fault)\b",
    r"\bpoor\s*(build\s*quality|material)\b",
    r"\b(broke|broken|scratch|chip|damage|crease)\b",
    r"\bfaulty\s*(part|component)\b",
    r"\b(plastic|cheap)\s*(material|feel)\b",
    r"\b(fade[sd]?|discolou?r|warped)\b",
    r"\b(fake|counterfeit)\b",
    r"\b(smell|stink|odor)\b",
]

FUNCTION_PATTERNS = [
    "不工作", "故障", "不能用", "功能缺失", "兼容性", "充不进电",
    r"\b(software|system)\s*(bug|issue|problem|update)\b",
    r"\b(screen|display)\s*(not\s*work|blank|glitch)\b",
    r"\bnavigation\s*(issue|problem)\b",
    r"\b(key\s*card|fob)\s*(not\s*work|problem)\b",
    r"\b(bluetooth|wifi|connectivity)\s*(issue|problem)\b",
    r"\bnfc\b|\brfid\b",
    r"\b(charging|charge)\s*(problem|issue|slow)\b",
    r"\b(range|anxiety)\s*(issue|problem)\b",
    r"\b(false\s*alarm|alarm\s*false|alarm\s*(going\s*off|problem|issue|malfunction))\b",
    r"\b(door|boot|trunk)\s*(won'?t\s*open|open\s*problem)\b",
    r"\b(trip\s*planner|navigation)\s*(doesn)?t\s*plan\b",
]

SERVICE_PATTERNS = [
    "退货难", "退款慢", "客服不理", "推诿", "拒绝保修", "维修收费高",
    r"\b(return|refund)\s*(process|difficult|slow)\b",
    r"\b(warranty|guarantee)\s*(denied|rejected|refused)\b",
    r"\b(service\s*center|dealership)\s*(no|nothing)\b.*\bcan\b",
    r"\bcustomer\s*service\s*(poor|bad|terrible|useless)\b",
    r"\b(dealer|dealership)\s*(ignored|didn'?t\s*help)\b",
    r"\brepair\s*(cost|price|expensive|overpriced)\b",
    r"\b(no\s*response|unresponsive|ignored)\b",
    r"\b(complaint|escalate[sd])\b",
    r"\b(legal|lawsuit|solicitor)\b",
]

SAFETY_PATTERNS = [
    "漏电", "起火", "爆炸", "有毒", "过热", "夹手", "锐利边缘",
    r"\b(fire|flame|burn)\b.*\b(battery|car|charging)\b",
    r"\b(smoke|burning\s*smell)\b",
    r"\b(explod\w*|explosion)\b",
    r"\b(overheat\w*|overheating)\b",
    r"\b(safety|danger)\s*(concern|issue|recall)\b",
    r"\brecall\b",
    r"\b(poison\w*|toxic)\s*(smell|gas|fume)\b",
    r"\b(brake|steering|accelerat)\w*\s*(fail|issue)\b",
]


# ============================================================
# 核心分析函数
# ============================================================

def _match_any(text: str, patterns: List[str]) -> int:
    """返回文本匹配到的模式数量"""
    text_lower = text.lower()
    return sum(1 for p in patterns if re.search(p, text_lower))


def analyze_sentiment(text: str) -> Tuple[str, int]:
    """
    双语情感分析
    返回: (情感标签, 强度分数)
    """
    strong_count = _match_any(text, STRONG_NEGATIVE_PATTERNS)
    if strong_count >= 1:
        return "强负面", 4

    neg_count = _match_any(text, NEGATIVE_PATTERNS)
    if neg_count >= 2:
        return "负面", 3
    if neg_count >= 1:
        return "负面", 3

    pos_count = _match_any(text, POSITIVE_PATTERNS)
    if pos_count >= 2:
        return "正面", 1
    if pos_count >= 1:
        return "正面", 1

    return "中性", 2


def classify_issue(text: str) -> str:
    """
    双语问题分类（按优先级：安全 > 质量 > 功能 > 售后 > 其他）
    """
    if _match_any(text, SAFETY_PATTERNS) > 0:
        return "安全风险"
    if _match_any(text, QUALITY_PATTERNS) > 0:
        return "质量问题"
    # 功能异常：false alarm / alarm malfunction 独立检测（优先级高于售后）
    if re.search(r"false\s*alarm|alarm\s*(going\s*off|malfunction|problem|issue)", text.lower()):
        return "功能异常"
    if _match_any(text, FUNCTION_PATTERNS) > 0:
        return "功能异常"
    if _match_any(text, SERVICE_PATTERNS) > 0:
        return "售后问题"
    return "其他"


def assess_severity(
    sentiment: str,
    sentiment_score: int,
    likes: int,
    comments: int,
    issue_type: str,
    user_influence: int = 2,
) -> Tuple[str, float]:
    """
    严重程度评估
    维度：情感强度(30%)、传播潜力(30%)、问题类型(25%)、用户影响力(15%)
    """
    emotion_score = sentiment_score  # 1-4

    total = likes + comments
    if total >= 100:
        spread_score = 4
    elif total >= 50:
        spread_score = 3
    elif total >= 10:
        spread_score = 2
    else:
        spread_score = 1

    type_scores = {
        "安全风险": 4, "质量问题": 3,
        "功能异常": 3, "售后问题": 2, "其他": 1
    }
    type_score = type_scores.get(issue_type, 1)

    # 强负面 + 高互动 → 强制升级
    if sentiment == "强负面" and total >= 20:
        type_score = max(type_score, 4)
        spread_score = max(spread_score, 3)

    total_score = (
        emotion_score * 0.3
        + spread_score * 0.3
        + type_score * 0.25
        + user_influence * 0.15
    )

    if total_score >= 3.5:
        return "严重", round(total_score, 2)
    elif total_score >= 2.5:
        return "高", round(total_score, 2)
    elif total_score >= 1.5:
        return "中", round(total_score, 2)
    else:
        return "低", round(total_score, 2)


def assess_spread_risk(likes: int, comments: int) -> str:
    """扩散风险评估"""
    total = likes + comments
    if total >= 100:
        return "高"
    elif total >= 50:
        return "中"
    return "低"


def generate_suggestion(issue_type: str, sentiment: str = "中性") -> str:
    """生成处理建议"""
    suggestions = {
        "质量问题": "建议联系售后换货，保留购买凭证，如多次投诉建议抽检同批次产品",
        "功能异常": "建议提交工单技术支持，必要时申请退换货，排查是否为个例或系统缺陷",
        "售后问题": "建议升级投诉级别，联系总部客服，记录工单编号跟进",
        "安全风险": "⚠️ 立即下架相关批次产品，进行安全检测，发布官方声明",
        "其他": "建议收集更多案例，分析是否为个案或系统性问题",
    }
    base = suggestions.get(issue_type, "常规处理")
    if sentiment == "强负面" and issue_type not in ["安全风险"]:
        base = "⚠️ " + base
    return base


def extract_keywords(text: str, top_n: int = 5) -> List[str]:
    """提取文本关键词（中英文）"""
    words = re.findall(r"[\w]{3,}", text.lower())
    stopwords = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
        "her", "was", "one", "our", "out", "day", "get", "has", "him", "his",
        "how", "its", "may", "new", "now", "old", "see", "two", "way", "who",
        "boy", "did", "she", "use", "this", "that", "with", "from", "they",
        "will", "have", "more", "been", "call", "come", "could", "each",
        "does", "else", "find", "give", "good", "have", "just", "know",
        "like", "look", "make", "most", "much", "name", "need", "only",
        "over", "part", "said", "some", "take", "than", "them", "then",
        "there", "these", "they", "thing", "think", "time", "very", "want",
        "well", "what", "when", "your", "also", "into", "than", "then",
        "的", "是", "了", "和", "在", "有", "一", "个", "这", "那",
        "我", "你", "他", "她", "它", "们", "不", "很", "都", "也",
        "就", "但", "因为", "所以", "如果", "虽然", "然后", "但是",
    }
    from collections import Counter
    word_freq = Counter(w for w in words if w not in stopwords)
    return [w for w, _ in word_freq.most_common(top_n)]


def analyze_post(post: Dict) -> Dict:
    """对单条帖子执行完整分析，返回增强后的字典"""
    text = post.get("content", "")
    sentiment, score = analyze_sentiment(text)
    issue_type = classify_issue(text)
    severity, sscore = assess_severity(
        sentiment, score,
        post.get("likes", 0),
        post.get("comments", 0),
        issue_type,
    )
    spread_risk = assess_spread_risk(post.get("likes", 0), post.get("comments", 0))
    suggestion  = generate_suggestion(issue_type, sentiment)
    keywords    = extract_keywords(text)

    return {
        **post,
        "sentiment":     sentiment,
        "sentiment_score": score,
        "issue_type":    issue_type,
        "severity":      severity,
        "severity_score": sscore,
        "spread_risk":  spread_risk,
        "suggestion":   suggestion,
        "keywords":     keywords,
    }


# ============================================================
# CLI 入口
# ============================================================

def main():
    if len(sys.argv) == 1:
        # 交互模式
        print("📝 输入帖子内容进行分析（Ctrl+D 结束输入）：")
        text = sys.stdin.read().strip()
        if not text:
            print("未输入内容")
            return
        post = {"content": text, "likes": 0, "comments": 0}
        result = analyze_post(post)
        _print_result(result)
        return

    if sys.argv[1] == "--file" and len(sys.argv) >= 3:
        # 批量模式
        with open(sys.argv[2]) as f:
            posts = json.load(f)
        results = [analyze_post(p) for p in posts]
        _print_summary(results)
        json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
        return

    # 单条模式
    text = " ".join(sys.argv[1:])
    post = {"content": text, "likes": 0, "comments": 0}
    result = analyze_post(post)
    _print_result(result)


def _print_result(r: Dict):
    print(f"\n📄 内容：{r['content'][:80]}{'...' if len(r['content']) > 80 else ''}")
    print(f"   情感：{r['sentiment']}（分数：{r['sentiment_score']}）")
    print(f"   分类：{r['issue_type']}")
    print(f"   严重程度：{r['severity']}（评分：{r['severity_score']}）")
    print(f"   扩散风险：{r['spread_risk']}")
    print(f"   建议：{r['suggestion']}")
    print(f"   关键词：{', '.join(r.get('keywords', []))}")


def _print_summary(results: List[Dict]):
    neg = [r for r in results if r["sentiment"] in ["强负面", "负面"]]
    alerts = [r for r in results if r["severity"] in ["严重", "高"]]
    print(f"\n📊 汇总：共 {len(results)} 条 | 负面 {len(neg)} 条 | 预警 {len(alerts)} 条\n")
    for r in results:
        flag = "🚨" if r["severity"] in ["严重", "高"] else "  "
        print(f"{flag} [{r['author']}] {r['sentiment']} | {r['issue_type']} | {r['severity']} | {r['suggestion'][:40]}...")


if __name__ == "__main__":
    main()
