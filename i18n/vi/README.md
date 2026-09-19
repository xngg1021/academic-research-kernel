# academic-research-kernel (vi)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Hạt nhân trung lập cho nghiên cứu học thuật và thảo luận đa tác tử. Cung cấp 13 kỹ năng học thuật và công cụ xác minh với các điểm truy cập di động Agent Plugins v1 và MCP (Model Context Protocol), cùng với sự tích hợp nguyên bản cho Hermes Agent, Claude Code, Cursor và các tác tử phụ CLI.

Tác giả: Junfu Shi (SJF, xngg1021), Hermes Agent. Giấy phép: [Source Lineage License 1.0](../../LICENSE).

## Giấy phép

Bản phát hành này áp dụng **Source Lineage License 1.0** cho các tài liệu được quy định trong [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Các bản ghi lịch sử trước `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` tiếp tục duy trì giấy phép MIT.

## Kỹ năng học thuật

| Kỹ năng | Phiên bản | Mô tả |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Xác minh chéo định danh và số lượng trích dẫn; kiểm tra tín hiệu cập nhật và rút bài báo; định vị văn bản truy cập mở và danh tính PDF |
| `skills/literature-analysis` | 1.3.0 | Mười hai quy trình: độ tương đồng chủ đề, trùng lặp văn bản, bằng chứng phản biện, hồ sơ tác giả, phản biện thử nghiệm và kiểm tra ngụy biện |
| `skills/academic-writing` | 1.1.1 | Biên tập học thuật, hướng dẫn trích dẫn (ISO 690, APA, MLA, Chicago, IEEE, AMA và hồ sơ khu vực), và quy định của tạp chí |
| `skills/math-computation` | 1.2.1 | Định tuyến miền toán học và thống kê với các công thức số học tính toán; tệp tham chiếu nâng cao |
| `skills/quantitative-paper-audit` | 1.1.0 | Tính toán lại các thống kê được công bố (kích thước hiệu ứng, giá trị p, khoảng tin cậy, OR/RR) và phát hiện sai lệch số liệu |
| `skills/research-reproducibility` | 1.0.1 | Quy trình kiểm toán khả năng tái lập 14 giai đoạn với danh mục kiểm tra có cấu trúc và hồ sơ tái lập minh bạch |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Nhật ký tìm kiếm PRISMA, sàng lọc tài liệu, chuyển đổi kích thước hiệu ứng, phân tích tính không đồng nhất và tổng hợp meta |
| `skills/literature-watch` | 1.1.0 | Giám sát hàng tuần: theo dõi chủ đề, tác giả và trích dẫn DOI trên OpenAlex và Crossref, tự động loại trừ trùng lặp |
| `skills/retraction-watch` | 1.1.0 | Giám sát hàng tuần: kiểm tra lại danh sách theo dõi DOI với chỉ mục rút bài và cập nhật từ OpenAlex và Crossref |
| `skills/research-object-identity` | 1.1.0 | Định danh tài nguyên nghiên cứu tất định và truy xuất nguồn gốc với xác thực đồ thị nhân quả DAG |
| `skills/claim-evidence-graph` | 1.0.0 | Liên kết tất định giữa luận điểm khoa học, hồ sơ bằng chứng và nguồn gốc tính toán |
| `skills/decision-ledger` | 1.0.0 | Nhật ký Quyết định Nghiên cứu: nhật ký chỉ ghi thêm tất định ghi lại các quyết định nghiên cứu, kết quả âm tính và trạng thái tuyến đường |
| `skills/cross-review-five` | 2.0.0 | Điều phối hội đồng đa phản biện động cho các mô hình không đồng nhất với phân bổ Kuhn-Munkres và thảo luận thưa v2 |

## Tiêu chuẩn Học thuật và Hồ sơ Đa quốc gia

Kho lưu trữ thiết lập **ISO 690:2021** (Tài liệu tham khảo thư mục), **ISO 5127:2017** (Khái niệm và từ vựng) và **W3C PROV** (Mô hình nguồn gốc) làm nền tảng quốc tế, cùng với các tiêu chuẩn chuyên ngành (APA 7th, IEEE, PRISMA 2020, ICMJE). Xem [Kiến trúc Tiêu chuẩn](../../docs/standards/README.md) và [Hướng dẫn Thuật ngữ](../../docs/terminology/README.md).

## Tích hợp và Sử dụng Di động

```bash
python scripts/mcp_server.py
```

## Xác minh và CI

CI thực thi toàn bộ bộ kiểm tra QA trên Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 và macOS Intel, với 625 bài kiểm tra đơn vị vượt qua và kiểm tra canary trực tiếp.

## Tài liệu Nghiên cứu và Kế hoạch

- [Bản đồ Điểm nghẽn v0 (Tiếng Anh)](../../docs/pain-atlas-v0.en.md), [Bản Tiếng Trung](../../docs/pain-atlas-v0.zh.md): Các rào cản trong chu trình nghiên cứu học thuật.
- [Kế hoạch Nghiên cứu v0 (Tiếng Anh)](../../docs/research-plan-v0.en.md), [Bản Tiếng Trung](../../docs/research-plan-v0.zh.md): Mô hình Research Object, các lĩnh vực năng lực cốt lõi và ma trận phân tích nhân tố.
