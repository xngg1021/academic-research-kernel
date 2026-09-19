# academic-research-kernel (fa)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

هسته خنثی برای تحقیقات دانشگاهی و مجموعه هم‌اندیشی چند عاملی. ارائه دهنده ۱۳ مهارت علمی و ابزار راستی‌آزمایی به همراه پلاگین‌های Agent Plugins v1 و سرور MCP با پشتیبانی مستقیم از Hermes Agent، Claude Code و Cursor.

نویسنده: Junfu Shi (SJF, xngg1021)، Hermes Agent. مجوز: [Source Lineage License 1.0](../../LICENSE).

## مجوز

این نسخه از مجوز **Source Lineage License 1.0** برای موارد مشخص شده در [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md) استفاده می‌کند. نسخه‌های قبلی تحت مجوز MIT معتبر باقی می‌مانند.

## مهارت‌های پژوهشی

| مهارت | نسخه | شرح |
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

## استانداردهای علمی و مبناهای چندگانه

این مخزن استانداردهای بین‌المللی **ISO 690:2021** (ارجاع‌دهی کتابشناختی)، **ISO 5127:2017** (مفاهیم و اصطلاحات) و **W3C PROV** (مدل ردگیری منشأ) را مبنا قرار می‌دهد. رجوع کنید به [معماری استانداردها](../../docs/standards/README.md) و [راهنمای اصطلاحات](../../docs/terminology/README.md).

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## راستی‌آزمایی و یکپارچه‌سازی مداوم

آزمون‌های مداوم (CI) بر روی پلتفرم‌های لینوکس، ویندوز و مک با ۶۲۵ تست واحد موفق و بررسی لحظه‌ای شاخه اصلی انجام می‌شود.

## اسناد پژوهش و برنامه‌ریزی

- [اطلس چالش‌ها v0 (انگلیسی)](../../docs/pain-atlas-v0.en.md)، [نسخه چینی](../../docs/pain-atlas-v0.zh.md): اصطکاک‌های موجود در چرخه فعالیت‌های علمی.
- [برنامه پژوهشی v0 (انگلیسی)](../../docs/research-plan-v0.en.md)، [نسخه چینی](../../docs/research-plan-v0.zh.md): مدل شیء پژوهشی، حوزه‌های قابلیت اصلی و ماتریس تجزیه عوامل.
