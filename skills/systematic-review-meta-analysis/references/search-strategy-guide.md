# 系统综述检索式构造与多数据库检索日志指南

配合 SKILL.md 的 PRISMA 流水线使用。目标:检索可复现,任何读者按日志能重跑出相同命中集。

## 1. 从问题到概念块

先把问题按 PICO(S) 拆成概念块,每块独立构造,块内 OR、块间 AND:

| 块 | 含义 | 示例(针刺治疗慢性腰痛) |
| --- | --- | --- |
| P | 人群/问题 | low back pain, chronic |
| I | 干预 | acupuncture, electroacupuncture, dry needling |
| C | 对照 | 通常不设块,靠 P 与 I 限定后人工筛 |
| O | 结局 | pain intensity, disability(仅在召回率过高时启用) |
| S | 研究设计 | randomized controlled trial |

每块同时覆盖两类词:
- 主题词:PubMed 用 MeSH(`"Low Back Pain"[Mesh]`),Embase 用 Emtree,Cochrane CENTRAL 同 MeSH。
- 自由词:同义词、拼写变体、缩写、截尾(`acupunct*`)与邻近算符(`near/3`、`adj3`,各库语法不同)。

新干预的主题词可能滞后数年,自由词块不能省。

## 2. 各库语法速查

| 数据库 | 字段标签 | 截尾 | 邻近 | 备注 |
| --- | --- | --- | --- | --- |
| PubMed | `[tiab]` `[Mesh]` | `*` | 无真正邻近,可用词组引号 | 自动词语映射可能吞掉精确式,检索日志里贴完整译后式 |
| Web of Science | `TS=` `TI=` | `*` `$` `?` | `NEAR/n` | `TS` 含题名摘要关键词 |
| Scopus | `TITLE-ABS-KEY()` | `*` `?` | `W/n` `PRE/n` | 机构订阅界面导出含完整式 |
| Embase | `:ti,ab,kw` `/exp` | `*` | `NEAR/n` | Emtree `/exp` 为扩展检索 |
| Cochrane CENTRAL | `:ti,ab,kw` MeSH | `*` | `near/n` | 综述注册的默认必备库 |
| CNKI/万方 | 主题字段 | 不支持英文式截尾 | 无 | 中文检索式单独记录,不混入英文 manifest |

## 3. 检索 manifest(机器可读)

每库一条记录,字段固定,存为 `search-manifest.yaml` 或直接写进 PRISMA 日志:

```yaml
- database: PubMed
  platform: NCBI
  searched_on: 2026-09-16
  query: '("Low Back Pain"[Mesh] OR "low back pain"[tiab]) AND ("Acupuncture Therapy"[Mesh] OR acupunct*[tiab]) AND (randomized controlled trial[pt])'
  limits: "2015-01-01 至检索日;humans"
  hits: 1234
  exported: pubmed-20260916.ris
```

规则:
- `query` 原样粘贴最终执行式,包括界面自动扩展后的版本(PubMed 页面底部可拷贝)。
- `searched_on` 是检索日,不是写作日;同一批库必须同一日检索。
- `hits` 以导出文件的记录数复核,不抄界面计数。
- 灰色文献(注册库、会议摘要、预印本)单独一条 manifest,注明检索方式不是布尔式时的实际步骤。

## 4. PRISMA 2020 流程数字来源

| 流程格 | 数字取自 |
| --- | --- |
| Identification | manifest 各库 `hits` 之和;去重前 |
| Duplicates removed | 去重账本(见 SKILL.md)的删除数,分 DOI 命中与标题模糊命中两行 |
| Records screened | 去重后进入题录筛的数量 |
| Records excluded | 题录筛排除数(一般不逐条记理由,但总数要平) |
| Reports sought / not retrieved | 全文获取成功与失败数,失败逐条记原因 |
| Reports excluded with reasons | 全文筛排除账本:每条记录 + 单一首要理由 + 排除阶段 |
| Studies included | 最终纳入数,与合成表行数一致 |

每个格子必须能由账本行数复算出来;复算不平就回头查,不许手改流程图数字。

## 5. 常见坑

- 不同库检索日不同 → 命中集不可比,更新检索要全库同日重跑。
- 只记界面命中数、不存导出文件 → 无法复核,务必留 RIS/BibTeX/nbib 原始导出。
- 去重只用 DOI → 预印本与正式发表同 DOI 家族、会议摘要无 DOI 会漏;DOI 命中后再跑一次规范化标题模糊匹配。
- 更新检索直接覆盖旧 manifest → 旧版本必须保留,PRISMA 要求分轮报告。
- 中文库导出编码混杂 → 统一转 UTF-8 后再入库,否则标题模糊去重会漏配。
