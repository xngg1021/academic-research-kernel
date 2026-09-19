# academic-research-kernel (pt)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Núcleo neutro de pesquisa acadêmica e conjunto de deliberação multiagente. Fornece 13 habilidades acadêmicas e ferramentas de verificação com pontos de entrada portáteis Agent Plugins v1 e MCP (Model Context Protocol), além de integração nativa para Hermes Agent, Claude Code, Cursor e subagentes CLI personalizados.

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Licença: [Source Lineage License 1.0](../../LICENSE).

## Licença

Este instantâneo adota a **Source Lineage License 1.0** para o material coberto identificado em [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Os instantâneos históricos até `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` mantêm a licença MIT original.

## Habilidades

| Habilidade | Versão | Descrição |
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

## Padrões Acadêmicos e Linha de Base Multi-Perfil

O repositório adota **ISO 690:2021** (Referências bibliográficas), **ISO 5127:2017** (Fundamentos e vocabulário) e **W3C PROV** (Modelo de proveniência) como linhas de base internacionais, ao lado de perfis regionais e normas disciplinares (APA 7th, IEEE, PRISMA 2020, ICMJE). Veja a [Arquitetura de Padrões](../../docs/standards/README.md) e o [Guia de Terminologia](../../docs/terminology/README.md).

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## Validação e CI

A integração contínua (CI) executa o conjunto completo de testes no Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 e macOS Intel, com 625 testes unitários aprovados e verificação de canary em tempo real.

## Documentos de Pesquisa e Planejamento

- [Atlas de Dores v0 (Inglês)](../../docs/pain-atlas-v0.en.md), [Versão em Chinês](../../docs/pain-atlas-v0.zh.md): Pontos de fricção no ciclo de trabalho acadêmico com verificação de fontes.
- [Plano de Pesquisa v0 (Inglês)](../../docs/research-plan-v0.en.md), [Versão em Chinês](../../docs/research-plan-v0.zh.md): Modelo Research Object, áreas de competência fundamentais e matriz de decomposição fatorial.
