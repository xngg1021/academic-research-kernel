# academic-research-kernel (bn)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

একাডেমিক গবেষণা এবং বহু-এজেন্ট পর্যালোচনার জন্য নিরপেক্ষ কার্নেল। এটি বহনযোগ্য Agent Plugins v1 এবং MCP (মডেল প্রসঙ্গ প্রোটোকল) সহ 13টি একাডেমিক দক্ষতা ও যাচাইকরণ সরঞ্জাম সরবরাহ করে, পাশাপাশি Hermes Agent, Claude Code, Cursor এবং CLI সাব-এজেন্টের সাথে কাজ করে।

লেখক: Junfu Shi (SJF, xngg1021), Hermes Agent. লাইসেন্স: [Source Lineage License 1.0](../../LICENSE).

## লাইসেন্স

এই স্ন্যাপশটটি [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md)-এ চিহ্নিত উপাদানের জন্য **Source Lineage License 1.0** গ্রহণ করে। ঐতিহাসিক সংস্করণগুলি MIT লাইসেন্সের অধীনে বৈধ থাকে।

## দক্ষতা

| দক্ষতা | সংস্করণ | বিবরণ |
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

## একাডেমিক মানদণ্ড এবং গ্লোবাল প্রোফাইল বেসলাইন

সংগ্রহস্থলটি আন্তর্জাতিক বেসলাইন হিসাবে **ISO 690:2021** (গ্রন্থপঞ্জিগত রেফারেন্স), **ISO 5127:2017** (শব্দভাণ্ডার) এবং **W3C PROV** (উৎস মডেল) প্রতিষ্ঠা করে। বিস্তারিত জানার জন্য [মানক আর্কিটেকচার](../../docs/standards/README.md) এবং [পরিভাষা নির্দেশিকা](../../docs/terminology/README.md) দেখুন।

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## যাচাইকরণ এবং সিআই

সিআই (CI) Linux x86_64, Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows এবং macOS জুড়ে 625টি সফল ইউনিট পরীক্ষা সহ সম্পূর্ণ QA স্যুট চালায়।

## গবেষণা ও পরিকল্পনা নথিপত্র

- [পেইন অ্যাটলাস v0 (ইংরেজি)](../../docs/pain-atlas-v0.en.md), [চীনা সংস্করণ](../../docs/pain-atlas-v0.zh.md): একাডেমিক জ্ঞান কাজের ঘর্ষণ বিন্দু।
- [গবেষণা পরিকল্পনা v0 (ইংরেজি)](../../docs/research-plan-v0.en.md), [চীনা সংস্করণ](../../docs/research-plan-v0.zh.md): রিসার্চ অবজেক্ট মডেল, মূল সক্ষমতার ক্ষেত্র এবং উপাদান বিশ্লেষণ ম্যাট্রিক্স।
