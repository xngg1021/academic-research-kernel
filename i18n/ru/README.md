# academic-research-kernel (ru)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Нейтральное ядро для академических исследований и комплекс мультиагентных обсуждений. Предоставляет 13 исследовательских навыков и инструментов верификации с переносимыми точками входа Agent Plugins v1 и MCP (Model Context Protocol), а также нативную интеграцию с Hermes Agent, Claude Code, Cursor и субагентами CLI.

Автор: Junfu Shi (SJF, xngg1021), Hermes Agent. Лицензия: [Source Lineage License 1.0](../../LICENSE).

## Лицензия

Настоящий репозиторий использует лицензию **Source Lineage License 1.0** в соответствии с [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Исторические коммиты до `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` сохраняют лицензию MIT.

## Исследовательские навыки

| Навык | Версия | Описание |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Cross-check identity and citation counts; inspect updates and retractions; locate OA text |
| `skills/literature-analysis` | 1.3.0 | Twelve workflows: similarity, overlap, counter-evidence, author profiles, mock reviews, fallacy checks |
| `skills/academic-writing` | 1.1.1 | Editing, citation guidance (ISO 690, APA, MLA, Chicago, IEEE, AMA and regional profiles), journal rules |
| `skills/math-computation` | 1.2.1 | Domain and task routing with numerical and statistical recipes; advanced reference files |
| `skills/quantitative-paper-audit` | 1.1.0 | Recompute reported statistics (effect size, p values, CIs, OR/RR, power) and detect discrepancies |
| `skills/research-reproducibility` | 1.0.1 | Fourteen-stage reproduction audit pipeline with structured checklists and reproducible records |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA search logs, screening logs, effect-size conversion, heterogeneity, and pooling |
| `skills/literature-watch` | 1.1.0 | Weekly blueprint: watch topics, authors, and DOI citing works on OpenAlex and Crossref |
| `skills/retraction-watch` | 1.1.0 | Weekly blueprint: monitor DOI watchlist against retraction indexes and update signals |
| `skills/research-object-identity` | 1.1.0 | Deterministic research-resource identification and provenance tracking; sub-100ms lineage tracing |
| `skills/claim-evidence-graph` | 1.0.0 | Deterministic scientific claim–evidence linking connecting assertions, evidence records, and provenance |
| `skills/decision-ledger` | 1.0.0 | Research Decision Log: deterministic log of research decisions, failed attempts, and route status |
| `skills/cross-review-five` | 2.0.0 | Dynamic multi-reviewer panel orchestration supporting heterogeneous models with Kuhn-Munkres matching |

## Академические стандарты и международные профили

Репозиторий устанавливает **ISO 690:2021** (Библиографические ссылки), **ISO 5127:2017** (Терминология и понятия) и **W3C PROV** (Модель происхождения) в качестве международных базовых линий, наряду с региональными профилями и дисциплинарными стандартами (APA 7th, IEEE, PRISMA 2020, ICMJE). См. [Архитектуру стандартов](../../docs/standards/README.md) и [Руководство по терминологии](../../docs/terminology/README.md).

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## Верификация и CI

Непрерывная интеграция (CI) запускает полный набор проверок QA на Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 и macOS Intel, с 625 успешно пройденными тестами и canary-проверкой.

## Исследовательские и плановые документы

- [Атлас проблемных зон v0 (англ.)](../../docs/pain-atlas-v0.en.md), [китайская версия](../../docs/pain-atlas-v0.zh.md): точки трения в академическом исследовательском цикле.
- [План исследований v0 (англ.)](../../docs/research-plan-v0.en.md), [китайская версия](../../docs/research-plan-v0.zh.md): модель Research Object, ключевые области возможностей и матрица факторизации.
