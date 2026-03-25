---
name: fb-public-opinion-monitor
description: >
  执行前先读取本技能目录下的 SOUL.md，它定义了你的分析风格和输出格式。
  Facebook 群组舆情监控与分析技能。通过 Browser Relay 自动进入 FB 群组、抓取帖子、截图，
  执行情感分析、问题分类、聚类检测、预警标记，最终输出结构化 Excel 报告。
  
  触发场景：
  - "分析 FB 群组 XXX 的舆情"
  - "监控 Facebook 群组 YYY 的负面反馈"
  - "抓取 FB 群组 ZZZ 最新帖子并分析"
  - "查看 Facebook 群组有没有负面评价"
  - 用户提到 Facebook 群组 + 舆情/负面/监控/分析 等关键词
  - 用户直接提供 Facebook 群组 URL（如 "https://www.facebook.com/groups/xxxxx"）
---

# Facebook 群组舆情监控

## 前置条件

**默认假设：** 用户已在浏览器, 已安装OpenClaw Browser Relay, 登录 Facebook 且完成人机验证

**异常处理：**
- 若检测到未登录/登录失效 → 直接打开 `https://www.facebook.com`，提示用户手动登录
- 登录完成后用户告知继续

## 工作模式

| 模式 | 帖子数 | 分析深度 | 适用场景 |
|------|--------|---------|---------|
| 快速扫描 | 10-20 | 基础分析 | 日常监控 |
| 标准分析 | 30-50 | 完整分析 | 周报/月报 |
| 深度分析 | 100+ | 含趋势对比 | 重大舆情事件 |

**默认模式：** 快速扫描

## 工作流程

### Step 1: 进入群组

**判断输入类型：**

```
IF 输入匹配 "https://www.facebook.com/groups/*"：
   → 直接使用 browser(action=navigate) 打开该 URL

ELSE IF 输入为群组名称：
   → 搜索群组并进入
   → 若未加入群组：申请加入/等待审核
```

**URL 匹配规则：**
- 匹配前缀：`https://www.facebook.com/groups/`
- 支持完整 URL 或带参数的 URL
- 示例：
  - `https://www.facebook.com/groups/769025288607803` ✓
  - `https://www.facebook.com/groups/769025288607803/?sorting_setting=RECENT_ACTIVITY` ✓

### Step 2: 抓取帖子 + 截图

```
对每个帖子抓取：
- 帖子截图（Complain 列唯一来源，优先级最高）
- 点赞数
- 评论数
- 发布时间
- 发布用户
- 帖子链接
- 粉丝评论（展开评论，抓取前 5-10 条热门回复）
```

> **⚠️ 核心原则：Complain 列一律使用截图，文本仅作兜底（截图全部失败时）。**
> 严禁在 Complain 列填入纯文本作为主要内容。

**抓取数量：** 默认至少 10 条最新帖子（按工作模式调整）
**进度反馈：** 每抓取 5 条帖子向用户汇报一次进度

---

#### 2.1 截图工具选择

| 优先级 | 工具 | 何时用 |
|--------|------|--------|
| **①** | MCP `browser(action=screenshot)` | 首选，群组页直接截，无需额外工具 |
| **②** | `fb_screenshot.ts` 脚本 | 批量截图，或需 Playwright 特殊处理时 |
| **③** | MCP `browser` + `act` 滚动后截图 | 需滚动定位元素后再截 |

截图保存目录（所有帖子统一）：
```
$WORKSPACE/fb_screenshots/{群组名sanitized}/
```
命名：`{post_id}.jpg`　例：`1726562752084355.jpg`

---

#### 2.2 MCP Browser 截图（首选，实时）

**标准单张截图流程：**

```
browser(action=navigate, url=<帖子URL>)
browser(action=wait, duration=3000)
browser(action=screenshot, fullPage=false)
→ 文件自动保存到 ~/.qclaw/media/browser/{uuid}.jpg

exec(command="mkdir -p $WORKSPACE/fb_screenshots/{群组sanitized}/
       && cp ~/.qclaw/media/browser/{uuid}.jpg $WORKSPACE/fb_screenshots/{群组sanitized}/{post_id}.jpg")
→ 复制到统一截图目录

# 记录到帖子数据
{ "post_id": "1726562752084355",
  "screenshot": "$WORKSPACE/fb_screenshots/MG_IM5_IM6_UK_Owners/1726562752084355.jpg",
  "likes": 11, "comments": 24, ... }
```

**滚动截取完整内容（长帖子）：**

```
browser(action=navigate, url=<帖子URL>)
browser(action=act, kind=press, key=PageDown)
browser(action=wait, duration=1500)
browser(action=act, kind=press, key=PageDown)
browser(action=wait, duration=1500)
browser(action=screenshot, fullPage=false)
→ 复制截图到统一目录
```

**滚动截取整页（展开评论后截图）：**

```
browser(action=navigate, url=<帖子URL>)
browser(action=act, kind=press, key=End)        # 滚到底触发懒加载
browser(action=wait, duration=2000)
browser(action=act, kind=press, key=Home)       # 回顶部
browser(action=wait, duration=1000)
browser(action=screenshot, fullPage=true)
```

**截取评论区域（评论已展开时）：**

```
browser(action=navigate, url=<帖子URL>)
browser(action=act, kind=press, key=PageDown)
browser(action=act, kind=press, key=PageDown)
browser(action=wait, duration=2000)
browser(action=screenshot, fullPage=false)
```

---

#### 2.3 fb_screenshot.ts 脚本（批量 / 离线备选）

> 前置条件：`npm install` + `npx playwright install chromium`

**单张：**
```bash
cd /Users/aaronyang/Desktop/sss/fb-public-opinion-monitor/scripts
npx tsx fb_screenshot.ts "<POST_URL>" "./screenshots/{post_id}.jpg"
```

**整页截图（长帖子 / 展开评论后）：**
```bash
npx tsx fb_screenshot.ts "<POST_URL>" "./screenshots/{post_id}.jpg" --full-page
```

**循环批量截图（抓取多条帖子时）：**

```typescript
import { fbScreenshot } from './scripts/fb_screenshot';

const screenshotDir = `${WORKSPACE}/fb_screenshots/${sanitizedGroupName}`;

const result = await fbScreenshot({
  url: postUrl,
  outputPath: `${screenshotDir}/${postId}.jpg`,
  viewport: { width: 1280, height: 720 },
  fullPage: false,
});

// 结果写入帖子数据
post.screenshot = result.success ? result.path : "";
```

---

#### 2.4 截图失败处理

```
截图失败时，按以下顺序重试：

① 重新 navigate + wait 3s → 再截一次
② 切换 fb_screenshot.ts 脚本截图
③ browser(action=screenshot, fullPage=true) 截整页

所有方式均失败 → Complain 列留空字符串
               → Remark 列末尾标注"[截图失败，请查看原文链接]"
               → 绝对不以纯文本填充 Complain 列
```

---

#### 2.5 粉丝评论抓取

```
1. 在帖子页面点击展开评论（[aria-label="查看更多评论"]）
2. 抓取前 5-10 条热门/最新评论
3. 记录格式：用户A: 评论内容1
用户B: 评论内容2...
4. 若评论区无法加载 → 标注"[评论区不可用]"
```

### Step 3: 舆情分析

**使用双语情感分析脚本（中英文关键词库）：**

```bash
# 单条测试
python3 scripts/analyze_sentiment.py "帖子正文内容"

# 批量分析（输出JSON）
python3 scripts/analyze_sentiment.py --file posts.json

# 交互模式
python3 scripts/analyze_sentiment.py
```

**分析维度：**

| 分析维度 | 说明 |
|---------|------|
| **情感判断** | 强负面 / 负面 / 中性 / 正面（支持中英文关键词） |
| **问题分类** | 安全风险 > 质量问题 > 功能异常 > 售后问题 > 其他 |
| **严重程度** | 低 / 中 / 高 / 严重（加权评分模型） |
| **聚类检测** | 相似关键词 + 同分类 + 时间窗口（7天）≥3条触发 |
| **扩散风险** | 低 / 中 / 高（基于点赞+评论总数） |
| **处理建议** | 按分类自动生成（中英双语措辞） |
| **🆕 事件溯源** | 追踪问题的起源、发展过程、相关帖子链条 |
| **🆕 问题演变** | 记录同一问题如何从初期投诉演变为聚类问题 |

**英文检测示例：**
- `false alarm / alarming issue` → 功能异常
- `terrible / disappointing` → 强负面
- `poor quality / faulty` → 质量问题
- `dealer said nothing they can do` → 售后问题
- `explosion / fire / toxic smell` → 安全风险

**中文检测示例：**
- `退货/退款/欺诈/假货` → 强负面
- `质量差/做工粗糙/破损` → 质量问题
- `客服不理/推诿/拒绝保修` → 售后问题

**情感分析规则：** 见 [references/sentiment_rules.md](references/sentiment_rules.md)

---

#### 3.1 事件溯源（新增）⭐

**目的：** 不仅分析情感，还要说明问题的来龙去脉

**溯源流程：**

```
1. 识别问题根源
   ├─ 初始投诉帖子（最早出现的相关投诉）
   ├─ 问题触发点（什么时间、什么事件引发）
   └─ 涉及产品/服务（具体是哪个产品或服务）

2. 追踪问题演变
   ├─ 第一阶段：初期投诉（1-2 条帖子）
   ├─ 第二阶段：问题扩散（3-5 条相似投诉）
   ├─ 第三阶段：聚类形成（≥5 条同类问题）
   └─ 第四阶段：舆论升级（高赞、高评论、预警触发）

3. 关联相关帖子
   ├─ 直接相关：同一产品、同一问题
   ├─ 间接相关：同一用户、同一地区、同一时间段
   └─ 衍生问题：由初期问题引发的后续投诉

4. 提取关键信息
   ├─ 问题首次出现时间
   ├─ 问题涉及的用户数量
   ├─ 问题的演变时间线
   └─ 问题的最新状态
```

**溯源示例：**

```
【事件溯源】

初始问题：DJI Osmo 360 电池续航不足
├─ 首次投诉：2026-03-21 (帖子 ID: 4410111795933167)
│  └─ 用户 Kim Santos: "3 month old with warranty from shop. Makinis na makinis"
│
├─ 问题扩散：2026-03-22 ~ 2026-03-23
│  ├─ 帖子 ID: 4415259168751763 - 用户询价
│  ├─ 帖子 ID: 4415403262070687 - 用户转卖（原因：不使用）
│  └─ 帖子 ID: 4415391795405167 - 用户询问配件
│
├─ 聚类形成：2026-03-24 ~ 2026-03-25
│  ├─ 相似投诉数：5 条
│  ├─ 核心关键词：续航、电池、不耐用
│  └─ 聚类 ID: CLUSTER_001
│
└─ 当前状态：
   ├─ 总涉及用户：8 人
   ├─ 总互动数：45 条评论
   ├─ 最高赞数：24 个赞
   └─ 风险等级：中等 ⚠️
```

**溯源数据结构：**

```json
{
  "cluster_id": "CLUSTER_001",
  "root_cause": "DJI Osmo 360 电池续航不足",
  "first_post_id": "4410111795933167",
  "first_post_time": "2026-03-21T10:30:00Z",
  "timeline": [
    {
      "phase": "初期投诉",
      "start_date": "2026-03-21",
      "end_date": "2026-03-21",
      "post_count": 1,
      "status": "单个投诉"
    },
    {
      "phase": "问题扩散",
      "start_date": "2026-03-22",
      "end_date": "2026-03-23",
      "post_count": 3,
      "status": "开始出现相似投诉"
    },
    {
      "phase": "聚类形成",
      "start_date": "2026-03-24",
      "end_date": "2026-03-25",
      "post_count": 5,
      "status": "形成明显聚类"
    }
  ],
  "related_posts": [
    {
      "post_id": "4410111795933167",
      "relation_type": "root_cause",
      "user": "Kim Santos",
      "content": "3 month old with warranty from shop. Makinis na makinis"
    },
    {
      "post_id": "4415259168751763",
      "relation_type": "similar_issue",
      "user": "匿名互动者",
      "content": "PTPA sino dito may 10k na drone..."
    }
  ],
  "affected_users": 8,
  "total_engagement": 45,
  "max_likes": 24,
  "risk_level": "中等"
}
```

---

#### 3.2 问题演变分析（新增）⭐

**目的：** 记录同一问题如何从初期投诉演变为聚类问题

**演变分析维度：**

```
1. 时间维度
   ├─ 问题首次出现时间
   ├─ 问题扩散速度（多久从 1 条变成 5 条）
   ├─ 问题活跃周期（是否有明显的高峰期）
   └─ 问题解决周期（问题是否在缓解）

2. 规模维度
   ├─ 投诉数量增长曲线
   ├─ 涉及用户数增长
   ├─ 互动数（赞+评论）增长
   └─ 扩散范围（地理位置、产品型号等）

3. 严重程度维度
   ├─ 初期：单个用户的个案投诉
   ├─ 中期：多个用户反映同类问题
   ├─ 后期：形成明显聚类，引发舆论关注
   └─ 危机：预警触发，需要立即处理

4. 用户情绪维度
   ├─ 初期情绪：失望、不满
   ├─ 中期情绪：愤怒、质疑
   ├─ 后期情绪：绝望、转向竞品
   └─ 危机情绪：公开谴责、呼吁抵制
```

**演变示例：**

```
【问题演变分析】

问题：DJI Osmo 360 电池续航不足

📈 规模演变
  Day 1 (2026-03-21)：1 条投诉
  Day 2 (2026-03-22)：2 条投诉 (+100%)
  Day 3 (2026-03-23)：3 条投诉 (+50%)
  Day 4 (2026-03-24)：5 条投诉 (+67%)
  Day 5 (2026-03-25)：5 条投诉 (稳定)

📊 严重程度演变
  初期 (Day 1)：低 - 单个用户投诉
  中期 (Day 2-3)：中 - 出现相似投诉
  后期 (Day 4-5)：中高 - 形成聚类，触发预警

😤 用户情绪演变
  初期：失望 ("Makinis na makinis" - 很失望)
  中期：质疑 ("为什么这么多人有同样问题？")
  后期：转向 ("考虑换其他品牌")

🔴 风险升级路径
  Day 1：个案 → Day 2-3：趋势 → Day 4-5：聚类 → Day 6+：危机？

💡 关键转折点
  - Day 2：第二条相似投诉出现（问题不是个案）
  - Day 4：第五条投诉出现（触发聚类预警）
  - 如果 Day 6 还有新投诉 → 升级为"严重舆情事件"
```

**演变预测：**

```
基于当前趋势，预测未来 7 天的发展：

乐观场景（30% 概率）：
  - 问题逐渐平息
  - 新投诉数量下降
  - 用户转向其他话题
  - 建议：继续监控，无需立即干预

中性场景（50% 概率）：
  - 问题保持当前水平
  - 每天 1-2 条新投诉
  - 形成稳定的聚类
  - 建议：发布官方回应，提供解决方案

悲观场景（20% 概率）：
  - 问题继续扩散
  - 每天 3+ 条新投诉
  - 引发媒体关注或大V转发
  - 建议：立即启动危机公关，发布声明
```

---

#### 3.3 Remark 字段的完整格式（更新）

```
【原文】{帖子完整内容}

【事件溯源】
  · 问题根源：{具体问题描述}
  · 首次出现：{时间}
  · 涉及产品：{产品名称}
  · 相关帖子：{帖子 ID 链接}
  · 涉及用户数：{数量}

【问题演变】
  · 初期状态：{Day 1 的情况}
  · 扩散过程：{Day 2-3 的情况}
  · 当前状态：{最新情况}
  · 演变趋势：{上升/平稳/下降}
  · 预测风险：{乐观/中性/悲观}

【AI分析】
  · 情感：{强负面/负面/中性/正面}
  · 分类：{质量问题/功能异常/售后问题/安全风险/其他}
  · 严重程度：{低/中/高/严重}
  · 扩散风险：{低/中/高}
  · 建议：{处理建议}

【聚类信息】
  · 聚类 ID：{cluster_id}
  · 聚类规模：{N 条相似投诉}
  · 核心关键词：{keyword1, keyword2, ...}
  · 聚类强度：{弱/中/强}
```

**完整示例：**

```
【原文】
For sale dji osmo 360 adventure combo. 3 month old with warranty from shop. 
Makinis na makinis. Angono, taytay, pasig area. Rfs - di nagagamit

【事件溯源】
  · 问题根源：DJI Osmo 360 电池续航不足，用户不满意
  · 首次出现：2026-03-21 10:30
  · 涉及产品：DJI Osmo 360 Adventure Combo
  · 相关帖子：4410111795933167, 4415259168751763, 4415403262070687
  · 涉及用户数：8 人

【问题演变】
  · 初期状态：单个用户投诉，仅 1 条帖子
  · 扩散过程：Day 2-3 出现 2 条相似投诉，Day 4-5 增至 5 条
  · 当前状态：形成明显聚类，触发预警
  · 演变趋势：上升（从 1 → 5 条，增长 400%）
  · 预测风险：中性（50% 概率保持当前水平，20% 概率继续扩散）

【AI分析】
  · 情感：负面
  · 分类：质量问题
  · 严重程度：中
  · 扩散风险：中
  · 建议：发布官方回应，说明电池续航的实际情况，提供保修或更换方案

【聚类信息】
  · 聚类 ID：CLUSTER_001
  · 聚类规模：5 条相似投诉
  · 核心关键词：续航、电池、不耐用、转卖
  · 聚类强度：中
```

### Step 4: 智能决策

**预警触发条件：**
- 单条帖子严重程度 = "严重"
- 强负面 + 点赞数 > 50
- 同类问题聚类 ≥ 3 条

**聚类触发条件：**
- 相似关键词 ≥ 3 个
- 同一问题分类 + 时间窗口 7 天内 ≥ 5 条

**知识库调用：**
- 检测到已知问题关键词 → 查询 `references/knowledge_base.md`
- 提取历史解决方案或官方回复

### Step 5: 输出报告

**使用 `build_report.py` 一键生成规范 Excel 报告（推荐）：**

```bash
cd /Users/aaronyang/Desktop/sss/fb-public-opinion-monitor/scripts

# 方式1：传入JSON文件（⚠️ 必须传递 --screenshots 参数！）
python3 build_report.py \
  --posts posts.json \
  --output /Users/aaronyang/Desktop/report.xlsx \
  --screenshots ./screenshots/ \
  --group "群组名称" \
  --date "2026-03-25"

# 方式2：从 stdin 传入 JSON（配合前一步分析）
python3 analyze_sentiment.py --file posts.json | python3 build_report.py \
  --auto \
  --output report.xlsx \
  --screenshots ./screenshots/ \
  --group "群组名称"
```

> **⚠️ 关键修复（2026-03-25）：Complain 列无图片问题**
>
> **问题症状：** Excel 报告中 Complain 列（B列）没有任何图片，文件大小很小（<10KB）
>
> **根本原因：** 
> 1. ❌ 缺少 `--screenshots` 参数 → 脚本无法找到截图文件
> 2. ❌ 截图目录为空 → 没有执行截图流程
> 3. ❌ 图片嵌入逻辑未触发 → `screenshot_dir` 参数为空字符串
>
> **解决方案（三步）：**
> 1. ✅ **为每个帖子截图** - 使用 Browser Relay 逐个访问帖子 URL 并截图
>    ```bash
>    for post_id in $(jq -r '.[].post_id' posts.json); do
>        browser.navigate("https://www.facebook.com/groups/.../posts/$post_id/")
>        browser.wait(2000)
>        screenshot=$(browser.screenshot())
>        cp $screenshot "fb_screenshots/$post_id.jpg"
>    done
>    ```
> 2. ✅ **传递 `--screenshots` 参数** - 告诉脚本截图目录在哪里
>    ```bash
>    python3 build_report.py \
>      --posts posts.json \
>      --output report.xlsx \
>      --screenshots /path/to/fb_screenshots/ \
>      --group "群组名称"
>    ```
> 3. ✅ **验证图片嵌入** - 检查 Excel 中是否有图片
>    ```python
>    from openpyxl import load_workbook
>    wb = load_workbook('report.xlsx')
>    ws = wb["详细分析"]
>    print(len(ws._images))  # 应该 > 0
>    ```
>
> **验证成功标志：**
> - ✅ 文件大小 > 1 MB（包含图片）
> - ✅ Complain 列（B列）显示帖子截图
> - ✅ `ws._images` 对象包含 N 张图片（N = 帖子数）

**输出 Excel 结构（单个 Sheet）：**

| Sheet | 内容 |
|-------|------|
| **舆情分析** | 主数据表，含截图、Like/Comments、原文+总结、粉丝评论 |

**详细分析 Sheet 格式规范：**

| 列 | 内容 | 格式说明 |
|----|------|---------|
| A 序号 | 1, 2, 3... | 居中；红色=严重，橙色=高，绿色=正面 |
| B **Complain** | **截图（420×260px）** | 截图列仅嵌入图片；截图失败时列内容留空 |
| C Like | 点赞数 | 居中 |
| D Comments | 评论数 | 居中 |
| E Remark | **原文 + 总结** | 格式：`原文：xxx\n\n总结内容：简短述说事情来龙去脉，情感倾向和诉求；问题类型；严重程度` |
| F Link | 帖子URL | 蓝色超链接字体 |
| G 粉丝评论 | 评论摘要 | 自动截断保留核心回复 |

**Complain 列截图嵌入规则：**

Complain 列（B列）= 嵌入截图图片（420×260px），**绝不放文本**

嵌入逻辑（`build_report.py` 自动处理）：
  1. 读取 post["screenshot"] 字段（截图文件路径）
  2. 若路径非空且文件存在 → `openpyxl.add_image()` 嵌入图片到 B 列
  3. 若路径为空或文件不存在 → B 列留空字符串（不禁用格，不填文本）

生成报告时帖子数据示例：
```json
{
  "post_id": "1726562752084355",
  "screenshot": "$WORKSPACE/fb_screenshots/MG_IM5_IM6_UK_Owners/1726562752084355.jpg",
  "likes": 11,
  "comments": 24,
  "content": "...",
  "link": "..."
}
```

> **⚠️ Complain 列（B列）规则：**
> - 有截图 → 嵌入图片（420×260px）
> - 无截图 → **列留空**，Remark 列末尾加 `[截图失败，请查看原文链接]`
> - 绝对禁止在 Complain 列填入任何文本内容

**Remark 字段格式：**
```
【原文】{帖子完整内容}

【AI分析】
  · 情感：{强负面/负面/中性/正面}
  · 分类：{质量问题/功能异常/售后问题/安全风险/其他}
  · 严重程度：{低/中/高/严重}
  · 扩散风险：{低/中/高}
  · 建议：{处理建议}
【聚类ID】：{cluster_id / 无}
```

### Step 6: 输出摘要

**向用户返回：**
1. 扫描统计：总帖数、负面占比、预警数量
2. 高风险问题 TOP3（按严重程度排序）
3. 聚类问题 TOP3（按帖子数排序）
4. 建议优先处理事项（3 条以内）

## 使用示例

**示例 1：通过群组名称**

**用户：** "分析 FB 群组 'XXX产品用户群' 的舆情"

**执行流程：**
1. 搜索群组 → 进入群组
2. 抓取最新 10+ 条帖子 + 截图 + 粉丝评论
3. 对每条帖子执行 AI 分析
4. 聚类相似问题
5. 标记高风险预警
6. 生成 Excel 报告
7. 返回报告路径 + 关键发现摘要

**示例 2：通过群组 URL（推荐）**

**用户：** "分析这个群组 https://www.facebook.com/groups/769025288607803"

**执行流程：**
1. 直接打开 URL → 检测登录状态
2. 若未登录 → 打开 fb.com 让用户登录
3. 抓取最新 10+ 条帖子 + 截图 + 粉丝评论
4. 对每条帖子执行 AI 分析
5. 聚类相似问题
6. 标记高风险预警
7. 生成 Excel 报告
8. 返回报告路径 + 关键发现摘要

## 增量分析

支持基于上次报告的时间戳，仅抓取新增帖子：
- 检查 `$WORKSPACE/fb_cache/last_scan.json` 中的时间戳
- 只抓取该时间戳之后的帖子
- 与历史数据合并生成完整报告
- 更新 `last_scan.json` 为最新时间

## 关键命令

### 浏览器操作

```javascript
// 导航到群组
browser(action=navigate, url="https://www.facebook.com/groups/xxx")

// 获取页面快照（用于解析帖子）
browser(action=snapshot)

// 展开评论（FB 动态加载，需先点击）
browser(action=click, selector="[aria-label='查看更多评论']")
browser(action=click, selector="[aria-label='View more comments']")

// 等待渲染（懒加载内容出现）
browser(action=wait, duration=2000)

// 👇 以下场景改用脚本方式截图片（见下方脚本命令）
// ❌ 不再推荐：browser(action=screenshot) 直接截帖子 —— 易截到空白或错误区域
// ✅ 推荐：先用 browser 定位+滚动，再用 fb_screenshot.ts 脚本截图
```

### 截图脚本命令（推荐）

> 截图脚本自动处理 FB 的懒加载、反爬虫检测、多策略降级，比纯 MCP screenshot 更可靠。

```bash
# 工作目录
cd /Users/aaronyang/Desktop/sss/fb-public-opinion-monitor/scripts

# 单张截图
npx tsx fb_screenshot.ts "<POST_URL>" "<OUTPUT_PATH>"

# 整页滚动截图（适合长帖子/多图）
npx tsx fb_screenshot.ts "<POST_URL>" "<OUTPUT_PATH>" --full-page

# 预览模式（不保存，仅调试截图策略）
npx tsx fb_screenshot.ts "<POST_URL>" "./preview.png" --dry-run
```

### Excel 生成

使用 `xlsx` skill 生成报告，配合 `openpyxl` 嵌入截图：

```python
from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XLImage
import os

def build_excel_report(posts_data: list, screenshot_base_dir: str, output_path: str):
    """生成含截图的 Excel 舆情报告"""
    wb = Workbook()
    ws = wb.active
    ws.title = "舆情分析"

    # 表头
    headers = ["序号", "Complain", "Like", "Comments", "Remark", "Link", "粉丝评论"]
    ws.append(headers)

    for idx, post in enumerate(posts_data, start=2):
        # Remark 内容（AI 分析摘要）
        remark_text = f"""【原文】{post.get('content', '')}

【AI分析】
- 情感：{post.get('sentiment', '未知')}
- 分类：{post.get('issue_type', '未知')}
- 严重程度：{post.get('severity', '未知')}
- 扩散风险：{post.get('spread_risk', '未知')}
- 建议：{post.get('suggestion', '')}"""

        row_data = [
            idx - 1,                  # 序号
            post.get('content', ''), # Complain（文字版兜底）
            post.get('likes', 0),    # Like
            post.get('comments', 0),# Comments
            remark_text,             # Remark
            post.get('link', ''),   # Link
            post.get('fan_comments', ''),  # 粉丝评论
        ]
        ws.append(row_data)

        # 嵌入截图（尝试从截图目录找到对应帖子文件）
        post_id = post.get('post_id', '')
        screenshot_dir = os.path.join(screenshot_base_dir, 'screenshots')
        if os.path.exists(screenshot_dir):
            matched = [f for f in os.listdir(screenshot_dir) if f.startswith(post_id)]
            if matched:
                img_path = os.path.join(screenshot_dir, matched[0])
                try:
                    img = XLImage(img_path)
                    img.width = 380
                    img.height = 280
                    # 截图放到 F 列（Link 列之后）
                    ws.add_image(img, f'F{idx}')
                except Exception as e:
                    print(f"⚠️ 截图嵌入失败 [{post_id}]: {e}")

    # 自动调整列宽
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 2, 60)

    wb.save(output_path)
    print(f"✅ 报告已生成: {output_path}")

# 使用示例
build_excel_report(
    posts_data=[
        {
            "post_id": "8765432109876543",
            "content": "产品质量太差了...",
            "likes": 50,
            "comments": 12,
            "sentiment": "强负面",
            "issue_type": "质量问题",
            "severity": "高",
            "spread_risk": "中",
            "suggestion": "建议联系售后换货",
            "link": "https://www.facebook.com/groups/xxx/posts/yyy",
            "fan_comments": "用户A: 确实有问题\n用户B: 期待解决",
        }
    ],
    screenshot_base_dir="/Users/aaronyang/Desktop/sss/fb-public-opinion-monitor",
    output_path="/Users/aaronyang/Desktop/facebook_public_opinion_20260325.xlsx"
)
```

**数据格式示例：**
```json
{
  "Complain": "（截图图片）",
  "Like": 50,
  "Comments": 20,
  "Remark": "原文：产品质量太差了...\n\n总结内容：希望可以解决质量产品问题，情感倾向：负面；问题类型：质量问题；严重程度：高",
  "Link": "https://www.facebook.com/groups/xxx/posts/yyy",
  "粉丝评论": "用户A: 评论内容1\n用户B: 评论内容2..."
}
```

## 错误处理

| 场景 | 处理 |
|------|------|
| 未登录/登录失效 | 打开 `https://www.facebook.com`，提示用户手动登录，完成后告知继续 |
| 遇到验证码 | 停止，提示用户完成验证 |
| 群组不存在 | 报错，请用户确认群组名称或 URL |
| 群组需审核 | 等待用户确认加入成功 |
| 截图失败 | 标注 "截图失败"，保留原文内容 |
| 评论无法加载 | 标注 "评论区不可用"，继续分析 |
| 帖子加载失败 | 跳过该帖子，记录日志 |
| **Complain 列无图片** | ⚠️ 见下方常见问题 |

### 常见问题排查

#### Q1: Excel 报告中 Complain 列（B列）没有任何图片？

**症状：**
- ❌ 文件大小很小（< 10 KB）
- ❌ B 列为空白
- ❌ 打开 Excel 后看不到帖子截图

**原因排查（按优先级）：**

1. **缺少 `--screenshots` 参数** ⚠️ 最常见
   ```bash
   # ❌ 错误
   python3 build_report.py --posts posts.json --output report.xlsx
   
   # ✅ 正确
   python3 build_report.py --posts posts.json --output report.xlsx \
     --screenshots /path/to/screenshots/
   ```

2. **截图目录为空或路径错误**
   ```bash
   # 检查目录是否存在且包含文件
   ls -lh /path/to/screenshots/
   # 应该看到 {post_id}.jpg 文件
   ```

3. **文件命名不匹配 post_id**
   ```bash
   # 文件名必须以 post_id 开头
   # ✅ 正确: 4415259168751763.jpg
   # ❌ 错误: screenshot_1.jpg, post.jpg
   ```

4. **没有执行截图流程**
   ```bash
   # 确保为每个帖子都执行了截图
   for post_id in $(jq -r '.[].post_id' posts.json); do
       browser.navigate("https://www.facebook.com/groups/.../posts/$post_id/")
       browser.wait(2000)
       screenshot=$(browser.screenshot())
       cp $screenshot "fb_screenshots/$post_id.jpg"
   done
   ```

**解决方案：**
1. 确保传递了 `--screenshots` 参数
2. 确保截图目录存在且包含 .jpg 文件
3. 确保文件名以 post_id 开头
4. 重新生成报告

**验证成功：**
```python
from openpyxl import load_workbook
wb = load_workbook('report.xlsx')
ws = wb["详细分析"]
print(f"嵌入图片数: {len(ws._images)}")  # 应该 > 0
```

#### Q2: 为什么 build_report.py 没有嵌入图片？

**原因：** `screenshot_dir` 参数为空或目录不存在

**源代码（第 475-490 行）：**
```python
if screenshot_dir and os.path.isdir(screenshot_dir):
    matched = [
        f for f in os.listdir(screenshot_dir)
        if f.startswith(str(post_id))
        and f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    if matched:
        img_path = os.path.join(screenshot_dir, matched[0])
        try:
            img = XLImage(img_path)
            img.width  = 420
            img.height = 260
            ws.add_image(img, f"B{row_num}")
        except Exception as e:
            print(f"  ⚠️ 截图嵌入失败 [{post_id}]: {e}")
```

**关键检查点：**
- ✓ `screenshot_dir` 参数已传递
- ✓ 目录存在且可读
- ✓ 文件名以 post_id 开头
- ✓ 文件格式为 .jpg/.png/.jpeg

#### Q3: 如何快速诊断问题？

**一键诊断脚本：**
```bash
#!/bin/bash

echo "🔍 诊断 Complain 列问题..."

# 1. 检查截图目录
SCREENSHOT_DIR="/Users/aaronyang/.qclaw/workspace/fb_screenshots/DJI_buy_and_sell_DJI_Mini_3_Supplier_Official_Distributor"
if [ -d "$SCREENSHOT_DIR" ]; then
    echo "✅ 截图目录存在"
    FILE_COUNT=$(ls -1 "$SCREENSHOT_DIR" | wc -l)
    echo "   包含 $FILE_COUNT 个文件"
else
    echo "❌ 截图目录不存在: $SCREENSHOT_DIR"
fi

# 2. 检查 Excel 文件
EXCEL_FILE="facebook_opinion_report_20260325_with_images.xlsx"
if [ -f "$EXCEL_FILE" ]; then
    SIZE=$(ls -lh "$EXCEL_FILE" | awk '{print $5}')
    echo "✅ Excel 文件存在，大小: $SIZE"
    if [ $(echo "$SIZE" | grep -o '[0-9]*' | head -1) -lt 100 ]; then
        echo "   ⚠️ 文件太小，可能没有嵌入图片"
    fi
else
    echo "❌ Excel 文件不存在"
fi

# 3. 检查 Excel 中的图片
python3 << 'EOF'
from openpyxl import load_workbook
try:
    wb = load_workbook('facebook_opinion_report_20260325_with_images.xlsx')
    ws = wb["详细分析"]
    if hasattr(ws, '_images'):
        print(f"✅ 发现 {len(ws._images)} 张图片")
    else:
        print("❌ 没有找到图片对象")
except Exception as e:
    print(f"❌ 无法打开 Excel: {e}")
EOF
```

## 参考资料

- [情感分析规则](references/sentiment_rules.md) — 负面关键词、分类规则
- [知识库](references/knowledge_base.md) — 已知问题、解决方案
- [聚类算法](references/clustering.md) — 相似度计算方法