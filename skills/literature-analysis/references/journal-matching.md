# 期刊匹配推荐（Journal Matching）

对应工作流 H。投稿前用主题标签反查发表过同类论文的期刊，输出候选期刊清单。

## 方法

1. 取论文 `topics` 和 `primary_topic`，按 ID 而非显示名称匹配；缺失时走明确标注的文本搜索兜底。
2. 每个 topic 用 `GET https://api.openalex.org/works?filter=topics.id:<TID>&group_by=primary_location.source.id&corpus=core` 聚合刊源，固定日期窗口和文献类型。如取 works 样本则 per_page<=100，用 cursor 分页并报告截断，不能将相关性排序前 100 篇频次当作全体期刊排名。
3. 对命中多个 topic 的 source 记录各自文献量、主题命中数与主主题是否命中。这是候选匹配启发式，不把 topic 分类分数当作录用率，也不将 Concepts 与 Topics 重复计分。
4. 查验候选来源的类型、ISSN、官方主页收录范围、近期发表文章以及投稿要求，严格区分学术期刊、学术会议与预印本仓储。sources?search 按刊名搜索，只能补充名称查找。无 ISSN、规模小或出版社不熟悉均不足以判为 predatory，需核查具体行为证据。

## 输出格式

| 候选期刊 | 命中主题 | 该刊相关论文量 | 类型/出版社 | 备注 |
| --- | --- | --- | --- | --- |

每刊附一行推荐理由（哪些主题重叠 + 该刊发表过的最接近论文示例 1~2 篇）。

## 诚实边界

- 中科院分区、JCR 影响因子以及期刊预警名单不在 OpenAlex 数据范围内，输出时明确注明“分区与影响因子需另行核对（借助 web_search 或由用户自行核对）”，严禁编造。
- 期刊匹配是主题邻近度推荐，不替代"读目标期刊最近几期判断口味"这一步。
- 会议场景同理：sources 里 `type=conference` 的条目即会议，可按同样方法匹配。
