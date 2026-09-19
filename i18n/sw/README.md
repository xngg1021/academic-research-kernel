# academic-research-kernel (sw)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Kiini kisichoegemea upande wowote cha utafiti wa kitaaluma na mashauriano ya mawakala wengi. Hutoa ujuzi 13 wa kitaaluma na zana za uthibitishaji na maingizo ya Agent Plugins v1 na MCP (Model Context Protocol), pamoja na muunganisho wa asili kwa Hermes Agent, Claude Code, Cursor, na mawakala wadogo wa CLI.

Mwandishi: Junfu Shi (SJF, xngg1021), Hermes Agent. Leseni: [Source Lineage License 1.0](../../LICENSE).

## Leseni

Toleo hili linatumia **Source Lineage License 1.0** kwa nyenzo zilizobainishwa katika [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Matoleo ya kihistoria yaliyopita chini ya leseni ya MIT yanaendelea kutumika.

## Ujuzi wa Kitaaluma

| Ujuzi | Toleo | Maelezo |
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

## Viwango vya Kitaaluma na Mwongozo wa Kimataifa

Hifadhi hii inaweka **ISO 690:2021** (Marejeleo ya kibibliografia), **ISO 5127:2017** (Msingi na msamiati), na **W3C PROV** (Muundo wa data wa asili) kama misingi ya kimataifa, sambamba na viwango vya kitaalamu (APA 7th, IEEE, PRISMA 2020, ICMJE). Tazama [Muundo wa Viwango](../../docs/standards/README.md) na [Mwongozo wa Istilahi](../../docs/terminology/README.md).

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## Uthibitishaji na CI

CI huendesha majaribio kamili ya QA kwenye mifumo ya Linux x86_64, Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows, na macOS, kukiwa na majaribio 625 ya vitengo yaliyofaulu na uthibitishaji wa moja kwa moja.

## Nyaraka za Utafiti na Mipango

- [Ramani ya Changamoto v0 (Kiingereza)](../../docs/pain-atlas-v0.en.md), [Toleo la Kichina](../../docs/pain-atlas-v0.zh.md): Changamoto katika mzunguko wa kazi za kitaaluma.
- [Mpango wa Utafiti v0 (Kiingereza)](../../docs/research-plan-v0.en.md), [Toleo la Kichina](../../docs/research-plan-v0.zh.md): Muundo wa Research Object, nyanja za uwezo wa msingi, na matriki ya uchambuzi wa vipengele.
