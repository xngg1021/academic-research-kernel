# academic-research-kernel (hi)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

अकादमिक अनुसंधान और बहु-एजेंट विचार-विमर्श के लिए तटस्थ कर्नेल। यह पोर्टेबल एजेंट प्लगइन्स v1 और MCP (मॉडल संदर्भ प्रोटोकॉल) प्रवेश बिंदुओं के साथ 13 अकादमिक कौशल और सत्यापन उपकरण प्रदान करता है, साथ ही हर्मीस एजेंट, क्लाउड कोड, कर्सर और सीएलआई उप-एजेंटों के लिए मूल एकीकरण प्रदान करता है।

लेखक: Junfu Shi (SJF, xngg1021), Hermes Agent. लाइसेंस: [Source Lineage License 1.0](../../LICENSE).

## लाइसेंस

यह स्नैपशॉट [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md) में पहचानी गई सामग्री के लिए **Source Lineage License 1.0** को अपनाता है। ऐतिहासिक स्नैपशॉट एमआईटी लाइसेंस के तहत मान्य रहते हैं।

## कौशल

| कौशल | संस्करण | विवरण |
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

## अकादमिक मानक और वैश्विक प्रोफाइल आधार रेखा

रिपॉजिटरी **ISO 690:2021** (ग्रंथ सूची संदर्भ), **ISO 5127:2017** (शब्दावली) और **W3C PROV** (उत्पत्ति डेटा मॉडल) को अंतरराष्ट्रीय आधार रेखा के रूप में स्थापित करती है। विस्तृत विवरण के लिए [मानक वास्तुकला](../../docs/standards/README.md) और [शब्दावली गाइड](../../docs/terminology/README.md) देखें।

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## सत्यापन और सीआई

सीआई (CI) Linux x86_64, Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 और macOS Intel पर 625 उत्तीर्ण इकाई परीक्षणों के साथ संपूर्ण QA सूट चलाता है।

## अनुसंधान और योजना दस्तावेज

- [दर्द एटलस v0 (अंग्रेजी)](../../docs/pain-atlas-v0.en.md), [चीनी संस्करण](../../docs/pain-atlas-v0.zh.md): अकादमिक ज्ञान कार्य जीवन चक्र में घर्षण बिंदु।
- [अनुसंधान योजना v0 (अंग्रेजी)](../../docs/research-plan-v0.en.md), [चीनी संस्करण](../../docs/research-plan-v0.zh.md): रिसर्च ऑब्जेक्ट मॉडल, मुख्य क्षमता क्षेत्र और कारक अपघटन मैट्रिक्स।
