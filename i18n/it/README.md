# academic-research-kernel (it)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Nucleo neutro per la ricerca accademica e suite di deliberazione multi-agente. Fornisce 13 competenze accademiche e strumenti di verifica con punti di ingresso portabili Agent Plugins v1 e MCP (Model Context Protocol), nonché integrazione nativa per Hermes Agent, Claude Code, Cursor e subagenti CLI.

Autore: Junfu Shi (SJF, xngg1021), Hermes Agent. Licenza: [Source Lineage License 1.0](../../LICENSE).

## Licenza

Questa versione adotta la **Source Lineage License 1.0** per il materiale coperto specificato in [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Gli snapshot storici fino a `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` mantengono la licenza MIT originale.

## Competenze

| Competenza | Versione | Descrizione |
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

## Standard Accademici e Baseline Multi-Profilo

Il repository stabilisce **ISO 690:2021** (Riferimenti bibliografici), **ISO 5127:2017** (Fondamenti e vocabolario) e **W3C PROV** (Modello di provenienza) come baseline internazionali, accanto a profili regionali e standard di settore (APA 7th, IEEE, PRISMA 2020, ICMJE). Consultare l'[Architettura degli Standard](../../docs/standards/README.md) e la [Guida Terminologica](../../docs/terminology/README.md).

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## Validazione e CI

La CI esegue l'intera suite QA su Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 e macOS Intel, con 625 test unitari superati e validazione canary upstream in tempo reale.

## Documenti di Ricerca e Pianificazione

- [Atlante delle Criticità v0 (Inglese)](../../docs/pain-atlas-v0.en.md), [Versione Cinese](../../docs/pain-atlas-v0.zh.md): Punti di attrito nel ciclo di lavoro accademico con verifica delle fonti.
- [Piano di Ricerca v0 (Inglese)](../../docs/research-plan-v0.en.md), [Versione Cinese](../../docs/research-plan-v0.zh.md): Modello Research Object, aree di competenza principali e matrice di scomposizione fattoriale.
