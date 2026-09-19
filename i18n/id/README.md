# academic-research-kernel (id)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Kernel netral untuk penelitian akademik dan rangkaian musyawarah multi-agen. Menyediakan 13 keterampilan akademik dan alat verifikasi dengan titik masuk portabel Agent Plugins v1 dan MCP (Model Context Protocol), serta integrasi bawaan untuk Hermes Agent, Claude Code, Cursor, dan sub-agen CLI.

Penulis: Junfu Shi (SJF, xngg1021), Hermes Agent. Lisensi: [Source Lineage License 1.0](../../LICENSE).

## Lisensi

Repositori ini mengadopsi **Source Lineage License 1.0** untuk materi yang dicakup dalam [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Komit historis hingga `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` tetap berada di bawah lisensi MIT.

## Keterampilan

| Keterampilan | Versi | Deskripsi |
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

## Standar Akademik dan Profil Multi-Wilayah

Repositori ini menetapkan **ISO 690:2021** (Referensi bibliografi), **ISO 5127:2017** (Fondasi dan kosakata) serta **W3C PROV** (Model data asal-usul) sebagai landasan internasional, bersama profil regional dan standar disiplin ilmu (APA 7th, IEEE, PRISMA 2020, ICMJE). Lihat [Arsitektur Standar](../../docs/standards/README.md) dan [Panduan Terminologi](../../docs/terminology/README.md).

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## Validasi dan CI

CI menjalankan rangkaian uji QA lengkap di Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64, dan macOS Intel, dengan 625 uji unit lolos dan validasi canary hulu langsung.

## Dokumen Penelitian dan Perencanaan

- [Atlas Titik Masalah v0 (Inggris)](../../docs/pain-atlas-v0.en.md), [Versi Bahasa Mandarin](../../docs/pain-atlas-v0.zh.md): Titik gesekan dalam siklus kerja akademik dengan status verifikasi bukti.
- [Rencana Penelitian v0 (Inggris)](../../docs/research-plan-v0.en.md), [Versi Bahasa Mandarin](../../docs/research-plan-v0.zh.md): Model Research Object, bidang kapabilitas inti, dan matriks dekomposisi faktor.
