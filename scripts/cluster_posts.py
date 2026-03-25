#!/usr/bin/env python3
"""
舆情聚类脚本
识别相似问题并进行分组
"""

import json
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import re


def tokenize(text: str) -> set:
    """
    简单分词：提取关键词集合
    """
    # 中英文分词
    words = re.findall(r'[\w]+', text.lower())
    
    # 去除停用词
    stopwords = {
        "的", "是", "了", "和", "在", "有", "一", "个", "这", "那", "我", "你", "他",
        "她", "它", "们", "不", "很", "都", "也", "要", "会", "能", "可以", "就",
        "还", "但", "因为", "所以", "如果", "虽然", "然后", "但是",
        "the", "is", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would", "could", "should"
    }
    
    return {w for w in words if w not in stopwords and len(w) >= 2}


def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两条文本的相似度（Jaccard 系数）
    """
    keywords1 = tokenize(text1)
    keywords2 = tokenize(text2)
    
    if not keywords1 or not keywords2:
        return 0.0
    
    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)
    
    return intersection / union if union > 0 else 0.0


def get_issue_type_keywords(issue_type: str) -> set:
    """
    获取问题分类对应的核心关键词
    """
    type_keywords = {
        "质量问题": {"质量", "破损", "瑕疵", "异味", "变形", "做工", "材质", "假货"},
        "功能异常": {"功能", "故障", "不能", "损坏", "兼容", "充电"},
        "售后问题": {"售后", "退货", "退款", "客服", "保修", "维修", "态度"},
        "安全风险": {"安全", "漏电", "起火", "爆炸", "有毒", "过热", "危险"},
        "其他": set()
    }
    return type_keywords.get(issue_type, set())


def check_cluster_criteria(post1: Dict, post2: Dict, similarity: float) -> bool:
    """
    检查是否满足聚类条件
    """
    # 条件1: 相似度阈值
    if similarity < 0.3:
        return False
    
    # 条件2: 同一问题分类
    if post1.get("issue_type") != post2.get("issue_type"):
        return False
    
    # 条件3: 时间窗口内（7天）
    try:
        time1 = datetime.strptime(post1.get("date", ""), "%Y-%m-%d")
        time2 = datetime.strptime(post2.get("date", ""), "%Y-%m-%d")
        if abs((time1 - time2).days) > 7:
            return False
    except:
        pass
    
    # 条件4: 核心关键词重叠
    type_kw1 = get_issue_type_keywords(post1.get("issue_type", ""))
    type_kw2 = get_issue_type_keywords(post2.get("issue_type", ""))
    
    if type_kw1 and type_kw2 and not (type_kw1 & type_kw2):
        # 同类型问题但关键词不重叠，需要更高相似度
        if similarity < 0.5:
            return False
    
    return True


def cluster_posts(posts: List[Dict]) -> List[List[Dict]]:
    """
    对帖子进行聚类
    返回: 聚类列表
    """
    if not posts:
        return []
    
    # 初始化：每个帖子一个簇
    clusters = [[i] for i in range(len(posts))]
    
    # 两两比较，合并满足条件的簇
    merged = True
    while merged:
        merged = False
        new_clusters = []
        used = set()
        
        for i in range(len(posts)):
            if i in used:
                continue
            
            current_cluster = [i]
            for j in range(i + 1, len(posts)):
                if j in used:
                    continue
                
                similarity = calculate_similarity(
                    posts[i].get("content", ""),
                    posts[j].get("content", "")
                )
                
                if check_cluster_criteria(posts[i], posts[j], similarity):
                    current_cluster.append(j)
                    used.add(j)
                    merged = True
            
            new_clusters.append(current_cluster)
            used.add(i)
        
        clusters = new_clusters
    
    # 只返回包含 2+ 帖子的聚类
    return [cluster for cluster in clusters if len(cluster) >= 2]


def assign_cluster_ids(posts: List[Dict], clusters: List[List[int]]) -> List[Dict]:
    """
    为帖子分配聚类 ID
    """
    # 创建日期前缀
    date_prefix = datetime.now().strftime("%Y%m%d")
    
    # 问题分类缩写
    type_abbrev = {
        "质量问题": "QL",
        "功能异常": "GN",
        "售后问题": "SH",
        "安全风险": "AQ",
        "其他": "OT"
    }
    
    # 初始化聚类ID为 None
    for post in posts:
        post["cluster_id"] = None
    
    # 分配聚类ID
    for idx, cluster in enumerate(clusters):
        if len(cluster) >= 2:
            issue_type = posts[cluster[0]].get("issue_type", "其他")
            abbrev = type_abbrev.get(issue_type, "OT")
            cluster_id = f"{date_prefix}_{abbrev}_{idx + 1:02d}"
            
            for post_idx in cluster:
                posts[post_idx]["cluster_id"] = cluster_id
    
    return posts


def generate_cluster_report(posts: List[Dict], clusters: List[List[int]]) -> List[Dict]:
    """
    生成聚类报告
    """
    reports = []
    date_prefix = datetime.now().strftime("%Y%m%d")
    type_abbrev = {
        "质量问题": "QL",
        "功能异常": "GN",
        "售后问题": "SH",
        "安全风险": "AQ",
        "其他": "OT"
    }
    
    for idx, cluster in enumerate(clusters):
        if len(cluster) >= 2:
            cluster_posts = [posts[i] for i in cluster]
            
            # 收集关键词
            all_keywords = set()
            for post in cluster_posts:
                keywords = tokenize(post.get("content", ""))
                all_keywords.update(keywords)
            
            # 统计主要问题类型
            issue_types = [post.get("issue_type") for post in cluster_posts]
            main_type = max(set(issue_types), key=issue_types.count)
            
            # 最高严重程度
            severities = {"严重": 4, "高": 3, "中": 2, "低": 1}
            max_severity = max(
                [severities.get(post.get("severity"), 1) for post in cluster_posts],
                default=1
            )
            max_severity_label = [k for k, v in severities.items() if v == max_severity][0]
            
            # 时间范围
            dates = [post.get("date") for post in cluster_posts if post.get("date")]
            
            # 生成建议
            suggestion = generate_cluster_suggestion(main_type, len(cluster), max_severity)
            
            report = {
                "cluster_id": f"{date_prefix}_{type_abbrev.get(main_type, 'OT')}_{idx + 1:02d}",
                "post_count": len(cluster),
                "time_range": f"{min(dates)} ~ {max(dates)}" if dates else "未知",
                "core_keywords": list(all_keywords)[:5],
                "main_issue": main_type,
                "max_severity": max_severity_label,
                "suggestion": suggestion
            }
            
            reports.append(report)
    
    return reports


def generate_cluster_suggestion(issue_type: str, count: int, severity: int) -> str:
    """
    为聚类生成处理建议
    """
    base_suggestion = {
        "质量问题": "建议抽检同批次产品，分析是否为系统性质保问题",
        "功能异常": "建议技术团队排查是否为共性缺陷",
        "售后问题": "建议优化售后服务流程，处理积压投诉",
        "安全风险": "⚠️ 需立即处理，可能涉及产品召回",
        "其他": "建议持续监控，判断是否为个案"
    }
    
    suggestion = base_suggestion.get(issue_type, "常规处理")
    
    if count >= 5:
        suggestion = f"【批量问题】{suggestion} 影响范围: {count} 条反馈"
    elif count >= 3:
        suggestion = f"【聚集问题】{suggestion}"
    
    return suggestion


if __name__ == "__main__":
    # 测试
    test_posts = [
        {
            "content": "产品质量太差了，用两天就坏了，做工很粗糙",
            "date": "2024-03-20",
            "issue_type": "质量问题",
            "severity": "中"
        },
        {
            "content": "质量真的不行，材质感觉很廉价",
            "date": "2024-03-21",
            "issue_type": "质量问题",
            "severity": "低"
        },
        {
            "content": "功能正常，就是质量有点差",
            "date": "2024-03-22",
            "issue_type": "质量问题",
            "severity": "低"
        },
        {
            "content": "客服态度很好，功能也不错",
            "date": "2024-03-20",
            "issue_type": "其他",
            "severity": "低"
        }
    ]
    
    clusters = cluster_posts(test_posts)
    print(f"发现 {len(clusters)} 个聚类")
    
    for i, cluster in enumerate(clusters):
        print(f"\n聚类 {i + 1}:")
        for post_idx in cluster:
            print(f"  - {test_posts[post_idx]['content']}")
    
    # 分配ID
    test_posts = assign_cluster_ids(test_posts, clusters)
    for post in test_posts:
        if post["cluster_id"]:
            print(f"\n帖子: {post['content'][:20]}... -> 聚类ID: {post['cluster_id']}")
    
    # 生成报告
    reports = generate_cluster_report(test_posts, clusters)
    print("\n聚类报告:")
    print(json.dumps(reports, ensure_ascii=False, indent=2))
