# academic-research-kernel (pl)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Neutralne jądro do badań akademickich i pakiet wieloagentowych narad. Zapewnia 13 umiejętności naukowych i narzędzi weryfikacyjnych z przenośnymi punktami wejścia Agent Plugins v1 i MCP (Model Context Protocol), a także natywną integrację dla Hermes Agent, Claude Code, Cursor i subagentów CLI.

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Licencja: [Source Lineage License 1.0](../../LICENSE).

## Licencja

Repozytorium przyjmuje **Source Lineage License 1.0** dla materiałów objętych licencją wskazanych w [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Historyczne migawki do `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` zachowują uprawnienia licencji MIT.

## Umiejętności

| Umiejętność | Wersja | Opis |
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

## Standardy Naukowe i Profile Wielojęzyczne

Repozytorium ustanawia **ISO 690:2021** (Przypisy bibliograficzne), **ISO 5127:2017** (Słownictwo i pojęcia) oraz **W3C PROV** (Model proweniencji) jako międzynarodowe linie bazowe, obok profili regionalnych i standardów dziedzinowych (APA 7th, IEEE, PRISMA 2020, ICMJE). Zobacz [Architekturę Standardów](../../docs/standards/README.md) oraz [Przewodnik Terminologiczny](../../docs/terminology/README.md).

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## Walidacja i CI

CI uruchamia pełny pakiet QA w systemach Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 i macOS Intel, z 625 zaliczonymi testami jednostkowymi i ciągłą weryfikacją kanarkową upstream.

## Dokumenty Badawcze i Planistyczne

- [Atlas Problemów v0 (angielski)](../../docs/pain-atlas-v0.en.md), [Wersja chińska](../../docs/pain-atlas-v0.zh.md): Punkty tarcia w cyklu pracy naukowej z weryfikacją źródeł.
- [Plan Badawczy v0 (angielski)](../../docs/research-plan-v0.en.md), [Wersja chińska](../../docs/research-plan-v0.zh.md): Model Research Object, kluczowe obszary kompetencji i macierz dekompozycji czynnikowej.
