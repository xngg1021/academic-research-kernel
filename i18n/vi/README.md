# academic-research-kernel (vi)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Hạt nhân trung lập cho nghiên cứu học thuật và thảo luận đa tác tử. Cung cấp 13 kỹ năng học thuật và công cụ xác minh với các điểm truy cập di động Agent Plugins v1 và MCP (Model Context Protocol), cùng với sự tích hợp nguyên bản cho Hermes Agent, Claude Code, Cursor và các tác tử phụ CLI.

Tác giả: Junfu Shi (SJF, xngg1021), Hermes Agent. Giấy phép: [Source Lineage License 1.0](../../LICENSE).

## Giấy phép

Bản phát hành này áp dụng **Source Lineage License 1.0** cho các tài liệu được quy định trong [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Các bản ghi lịch sử trước `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` tiếp tục duy trì giấy phép MIT.

## Kỹ năng học thuật

| Kỹ năng | Phiên bản | Mô tả |
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

## Tiêu chuẩn Học thuật và Hồ sơ Đa quốc gia

Kho lưu trữ thiết lập **ISO 690:2021** (Tài liệu tham khảo thư mục), **ISO 5127:2017** (Khái niệm và từ vựng) và **W3C PROV** (Mô hình nguồn gốc) làm nền tảng quốc tế, cùng với các tiêu chuẩn chuyên ngành (APA 7th, IEEE, PRISMA 2020, ICMJE). Xem [Kiến trúc Tiêu chuẩn](../../docs/standards/README.md) và [Hướng dẫn Thuật ngữ](../../docs/terminology/README.md).

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## Xác minh và CI

CI thực thi toàn bộ bộ kiểm tra QA trên Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 và macOS Intel, với 625 bài kiểm tra đơn vị vượt qua và kiểm tra canary trực tiếp.

## Tài liệu Nghiên cứu và Kế hoạch

- [Bản đồ Điểm nghẽn v0 (Tiếng Anh)](../../docs/pain-atlas-v0.en.md), [Bản Tiếng Trung](../../docs/pain-atlas-v0.zh.md): Các rào cản trong chu trình nghiên cứu học thuật.
- [Kế hoạch Nghiên cứu v0 (Tiếng Anh)](../../docs/research-plan-v0.en.md), [Bản Tiếng Trung](../../docs/research-plan-v0.zh.md): Mô hình Research Object, các lĩnh vực năng lực cốt lõi và ma trận phân tích nhân tố.
