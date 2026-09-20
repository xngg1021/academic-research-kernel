# academic-research-kernel (vi)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Nhân nghiên cứu học thuật trung lập với nền tảng và bộ công cụ thảo luận đa tác tử. Cung cấp 13 kỹ năng học thuật và công cụ xác thực với các điểm nhập Agent Plugins v1 và MCP (Model Context Protocol), cũng như tích hợp gốc cho Hermes Agent, Claude Code, Cursor và các tác tử phụ CLI tùy chỉnh. Bao gồm xác minh nguồn, phân tích tài liệu, biên tập học thuật, tính toán số học, kiểm toán bài báo định lượng, kiểm toán khả năng tái lập, tổng quan hệ thống và phân tích tổng hợp, danh tính và nguồn gốc đối tượng nghiên cứu, điều phối phản biện chéo đa mô hình động và hai dịch vụ giám sát tự động hàng tuần. Kho lưu trữ bao gồm các kiểm tra ví dụ có thể thực thi; phạm vi xác thực và giới hạn dịch vụ bên ngoài được ghi lại trong [kiểm toán](../../docs/project-lineage-audit-20260920.md).

Tác giả: Junfu Shi (SJF, xngg1021), Hermes Agent. Cung cấp cấp phép hiện tại: [Source Lineage License 1.0](../../LICENSE).

## Giấy phép

Bản chụp chứa thông báo này áp dụng **Source Lineage License 1.0** cho Tài liệu Được bảo hộ và các quyền được xác định trong [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Bản commit và cây SLL đầu tiên, cùng bản commit ghi lại ranh giới sau đó, được phân biệt trong [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) và [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md).

Các bản chụp lịch sử cho đến `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` được cấp phép theo MIT. Người nhận giữ nguyên các quyền MIT hợp lệ và không cần chuyển sang SLL. [Văn bản MIT trước đây của dự án](../../LICENSES/MIT-pre-SLL.txt) được bảo tồn; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) và nguồn gốc bên thứ ba không thay đổi. Cung cấp gốc mới không xóa bỏ các quyền đó.

SLL cho phép rộng rãi việc sử dụng, nghiên cứu, sửa đổi, sử dụng thương mại, phân phối và bổ sung độc quyền, tuân theo các điều kiện áp dụng về giấy phép, thông báo và nguồn gốc xuất xứ. Đây không phải là copyleft và không yêu cầu tiết lộ mã nguồn. Văn bản tiếng Anh chính xác của [LICENSE](../../LICENSE) chi phối tóm tắt thông tin này; `LicenseRef-Source-Lineage-1.0` là tham chiếu cục bộ, không phải mã định danh SPDX. [Tiếp nhận đóng góp](../../CONTRIBUTING.md) tách biệt với các quyền cấp phép hạ nguồn.

## Kỹ năng

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

Có 21 tệp tham chiếu Markdown trên mười ba kỹ năng. Tài liệu tham khảo chỉ được tải khi cần thiết.

## Tiêu chuẩn Học thuật và Đường cơ sở Đa hồ sơ

Quy cách trích dẫn, tiêu chí báo cáo và siêu dữ liệu phụ thuộc vào tạp chí, tổ chức, nhà tài trợ, ngành học và khu vực tài phán. Kho lưu trữ thiết lập **ISO 690:2021** (Tài liệu tham khảo thư mục), **ISO 5127:2017** (Từ vựng thông tin và tư liệu) và **W3C PROV** (Mô hình dữ liệu nguồn gốc) làm tiêu chuẩn quốc tế, bên cạnh các hồ sơ khu vực và quy chuẩn ngành (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Xem [Kiến trúc Tiêu chuẩn](../../docs/standards/README.md) và [Hướng dẫn Thuật ngữ Tự nhiên](../../docs/terminology/README.md).

## Tích hợp và Sử dụng Di động

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
Kho lưu trữ này tuân thủ đặc tả trung lập **Agent Plugins v1** (`../../plugin.json`) và hiển thị các công cụ xác thực học thuật và tính toán thống kê cốt lõi thông qua **máy chủ MCP** stdio (`../../mcp.json` / `python scripts/mcp_server.py`). Tương thích với Claude Code, Cursor, Gemini CLI và bất kỳ khung tác tử hiện đại nào.

```bash
# Add as stdio MCP server in your agent harness
python scripts/mcp_server.py
```

### 2. Cài đặt Gốc trong Hermes
Từ môi trường cài đặt Hermes, hãy chạy:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Cài đặt các kỹ năng khác bằng cách thay thế tên thư mục trong mã định danh đầy đủ. Tap tiêu chuẩn đọc nhánh mặc định. Các kỹ năng liên quan đi kèm được xác minh tại commit `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video.

## Truy cập Nguồn Dữ liệu

- Các truy vấn cơ bản của OpenAlex có thể chạy ẩn danh với ngân sách hàng ngày nhỏ ($0.10/ngày ẩn danh và $1/ngày với khóa API miễn phí, giới hạn 100 yêu cầu/giây). Lưu khóa tùy chọn trong `OPENALEX_API_KEY`.
- Crossref cung cấp quyền truy cập siêu dữ liệu công khai có điều tiết tốc độ. Tín hiệu cập nhật và Retraction Watch yêu cầu kiểm tra DOI.
- Unpaywall yêu cầu email liên hệ thực trong `UNPAYWALL_EMAIL`.
- arXiv, Europe PMC, PubMed và DOAJ là các nguồn bổ sung có chính sách riêng. Scite, Dimensions, Scopus và Web of Science là các dịch vụ bên ngoài tùy chọn.

## Xác thực

Sử dụng môi trường Python chuyên dụng. Các phụ thuộc QA bao gồm tất cả các kiểm tra có thể thực thi:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA xác thực siêu dữ liệu, tài liệu tham khảo, đường dẫn cá nhân/mô hình bí mật, cú pháp Python và các khối mã được đánh dấu. Trả về 0 khi thành công, 1 khi lỗi mã/lược đồ/danh tính và 2 khi không thể truy cập truyền tải/xác thực/hạn ngạch.

CI chạy bộ thử nghiệm đầy đủ trên Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview, Windows x86_64, Windows ARM64, macOS ARM64 và macOS Intel, với 703 bài kiểm tra đơn vị đã qua và 40 khối mã thực thi được xác thực.

tools/longtail/ chứa bộ tạo kịch bản đuôi dài cực đoan tất định: 4096 kết hợp ứng viên hạt giống SHA256 trên các trục nhân tố tách rời, lựa chọn độ bao phủ tham lam và báo cáo độ bao phủ trong generated-scenarios.json.

scripts/scfabric/ là cấu trúc tính toán khoa học: thăm dò phần cứng, danh mục phụ trợ với cổng kiểu dữ liệu, năm hồ sơ khối lượng công việc và ComputeReceipt. Đo lường được ghi lại trong [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md).

## Tài liệu Nghiên cứu và Kế hoạch

Các tài liệu này là tài liệu tham khảo lập kế hoạch khám phá, không phải là lộ trình ràng buộc.

- [Tập bản đồ Điểm nghẽn v0 (tiếng Anh)](../../docs/pain-atlas-v0.en.md), [Bản tiếng Trung](../../docs/pain-atlas-v0.zh.md): Các điểm ma sát trong vòng đời nghiên cứu học thuật.
- [Kế hoạch Nghiên cứu v0 (tiếng Anh)](../../docs/research-plan-v0.en.md), [Bản tiếng Trung](../../docs/research-plan-v0.zh.md): Mô hình Research Object, các lĩnh vực năng lực cốt lõi và ma trận phân rã nhân tố.
