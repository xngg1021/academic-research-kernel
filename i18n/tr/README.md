# academic-research-kernel (tr)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Akademik araştırmalar ve çoklu ajan istişareleri için bağımsız çekirdek. Taşınabilir Agent Plugins v1 ve MCP (Model Context Protocol) giriş noktaları ile 13 akademik beceri ve doğrulama aracı sağlar; ayrıca Hermes Agent, Claude Code, Cursor ve özel CLI alt ajanları için yerel entegrasyon sunar.

Yazar: Junfu Shi (SJF, xngg1021), Hermes Agent. Lisans: [Source Lineage License 1.0](../../LICENSE).

## Lisans

Bu anlık görüntü, [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md) dosyasında tanımlanan materyaller için **Source Lineage License 1.0** lisansını benimser. `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` öncesindeki geçmiş kopyalar MIT lisansı kapsamındadır.

## Beceriler

| Beceri | Sürüm | Açıklama |
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

## Akademik Standartlar ve Çoklu Profil Temeli

Depo, **ISO 690:2021** (Bibliyografik referanslar), **ISO 5127:2017** (Temel kavramlar ve sözlük) ve **W3C PROV** (Köken veri modeli) standartlarını uluslararası temel olarak kabul eder. Ayrıntılar için [Standartlar Mimarisi](../../docs/standards/README.md) ve [Terminoloji Kılavuzu](../../docs/terminology/README.md) belgelerine bakınız.

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## Doğrulama ve CI

CI, tam QA paketini Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 ve macOS Intel ortamlarında, 625 başarılı birim testi ve canlı upstream canary doğrulaması ile çalıştırır.

## Araştırma ve Planlama Belgeleri

- [Zorluklar Atlası v0 (İngilizce)](../../docs/pain-atlas-v0.en.md), [Çince Sürüm](../../docs/pain-atlas-v0.zh.md): Akademik bilgi çalışması döngüsündeki sürtünme noktaları.
- [Araştırma Planı v0 (İngilizce)](../../docs/research-plan-v0.en.md), [Çince Sürüm](../../docs/research-plan-v0.zh.md): Research Object modeli, temel yetenek alanları ve faktör ayrıştırma matrisi.
