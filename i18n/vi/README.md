# academic-research-kernel (vi)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Bộ công cụ và nền tảng quản lý trạng thái nghiên cứu học thuật tất định dành cho các quy trình nghiên cứu có hỗ trợ tác tử tự hành, hoạt động độc lập với môi trường chạy. Hệ thống hợp nhất định danh đối tượng nghiên cứu, bản ghi bằng chứng / xác minh thực nghiệm, mối quan hệ giữa luận điểm và bằng chứng (CEG) cùng nhật ký quyết định nghiên cứu và thử nghiệm thất bại chỉ ghi thêm thông qua tầng tiếp nhận và phân tích tài liệu nghiên cứu tất định cũng như máy chủ Model Context Protocol (MCP) phổ quát. 14 kỹ năng học thuật chuyên biệt vừa tạo lập vừa khai thác trạng thái nghiên cứu đã được kiểm chứng, hỗ trợ trực tiếp cho Claude Code, Cursor, Codex, Gemini CLI và Hermes Agent. Phạm vi kiểm định và giới hạn của các dịch vụ bên ngoài được ghi nhận tại [báo cáo kiểm định](../../docs/project-lineage-audit-20260920.md).

Tác giả: Junfu Shi (SJF, xngg1021), Hermes Agent. Phạm vi cấp phép hiện hành: [Source Lineage License 1.0](../../LICENSE).

## Bắt đầu nhanh

Chạy phiên bản 2.1.0 bằng [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx academic-research-kernel@2.1.0 mcp
```

[Bản phát hành 2.1.0](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0) ghi lại mã băm của các gói phân phối và trạng thái công bố. Gói wheel phát hành cũng có thể chạy cục bộ bằng lệnh `uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`. Hệ thống hỗ trợ Python 3.10–3.14; tùy chọn `uvx --python 3.12` cho phép chỉ định rõ trình thông dịch được hỗ trợ. Toàn bộ 12 công cụ tất định cùng bộ công cụ tính toán khoa học và thống kê đều có sẵn ngay trong bản cài đặt cơ bản.

## Kiểm tra cài đặt

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

Trình chẩn đoán ngoại tuyến kiểm tra các thư viện phụ thuộc, lược đồ dữ liệu và toàn bộ 12 định nghĩa công cụ. Các dịch vụ bên ngoài tùy chọn có thể để trống mà không gây lỗi. Sử dụng `doctor --json` để nhận kết quả ở định dạng máy đọc được.

## Cài đặt gói phần mềm

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Ngoài ra, bạn có thể cài đặt bằng `pipx install academic-research-kernel==2.1.0` hoặc chạy `python -m pip install academic-research-kernel==2.1.0` bên trong một môi trường ảo được hỗ trợ. Tùy chọn `[full]` bổ sung các thư viện cho những ví dụ tính toán khoa học mở rộng; `[qa]` bổ sung công cụ kiểm định kho lưu trữ bao gồm trình phân tích PDF. Tùy chọn `[research]` cài đặt `pypdf==6.19.0` và `fonttools==4.65.0` nhằm bảo đảm giải mã phông chữ PDF nhất quán trên các môi trường cài đặt mới; cả hai đều tương thích với Python 3.10. Việc đọc HTML/XML có cấu trúc và DOCX/XLSX giới hạn dung lượng sử dụng thư viện chuẩn của Python. Các phụ trợ GPU và dịch vụ trả phí vẫn là tùy chọn không bắt buộc.

## Hermes

Cài đặt uv sao cho biến môi trường PATH của tiến trình Hermes nhận diện được, sau đó cài đặt và kích hoạt tường minh plugin di động:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

Tên định danh `academic-skills` hiện có được giữ nguyên để tương thích ngược và bao gồm đủ 14 kỹ năng, trong đó có `paper-research`. Tệp `mcp.json` của plugin gọi `uv run --frozen --no-dev --no-editable` với Python 3.12 cùng tệp khóa `uv.lock` của kho mã nguồn; môi trường thực thi độc lập được đặt tại `${PLUGIN_DATA}/runtime`. Trong lần chạy đầu tiên, plugin tự động khởi tạo các gói phụ thuộc mà không mượn thư viện Python của Hermes hay của hệ điều hành. Lần khởi chạy đầu tiên cần kết nối mạng để tải trình thông dịch hoặc gói còn thiếu. Phương thức cài đặt chỉ lấy kỹ năng qua tap cũ vẫn được hỗ trợ tại mục tích hợp di động bên dưới.

## Chạy từ mã nguồn

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Xem [tài liệu phân phối và phát hành](../../docs/distribution-release.md) để nắm rõ phân loại phụ thuộc, quy trình tái lập, định danh bản phát hành, các mốc kiểm tra công bố và phạm vi xác thực.

## Giấy phép

Bản chụp chứa thông báo này áp dụng **Source Lineage License 1.0** cho Tài liệu Được bảo hộ và các quyền được xác định trong [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Bản commit và cây thư mục SLL đầu tiên, cùng bản commit ghi nhận ranh giới chuyển đổi sau đó, được phân biệt rõ trong [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) và [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Các bản chụp kể từ mốc chuyển đổi đã ghi nhận trở đi nếu giữ lại thông báo này đều mang cùng phạm vi cấp phép.

Các bản chụp lịch sử cho đến `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` được cấp phép theo MIT, tuân theo các điều khoản áp dụng cho những bản sao đó. Người nhận giữ nguyên các quyền MIT hợp lệ và không bắt buộc phải chuyển sang SLL. [Văn bản MIT trước đây của dự án](../../LICENSES/MIT-pre-SLL.txt) vẫn được lưu giữ; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) và nguồn gốc bên thứ ba của tệp này không thay đổi. Đề nghị cấp phép mới ở thư mục gốc không xóa bỏ các quyền sẵn có đó.

SLL cho phép rộng rãi việc sử dụng, nghiên cứu, sửa đổi, khai thác thương mại, phân phối và bổ sung phần mở rộng độc quyền, miễn là tuân thủ các điều kiện về giấy phép, thông báo và nguồn gốc xuất xứ. Đây không phải là giấy phép copyleft và không yêu cầu công khai mã nguồn. Việc cung cấp dịch vụ thuần túy qua mạng mà không phân phối bản sao tự thân nó không kích hoạt điều kiện thông báo nguồn gốc dịch vụ Core. Giấy phép không cấp quyền sáng chế tường minh. Tài liệu của bên thứ ba vẫn tuân theo điều khoản riêng của chúng. Văn bản tiếng Anh chính thức tại [LICENSE](../../LICENSE) có giá trị pháp lý cao nhất đối với bản tóm tắt thông tin này; `LicenseRef-Source-Lineage-1.0` là mã tham chiếu cục bộ chứ không phải mã định danh SPDX, và dự án không tuyên bố đã được OSI phê duyệt. Quy định [tiếp nhận đóng góp](../../CONTRIBUTING.md) tách biệt với các quyền cấp phép cho người dùng hạ nguồn.

## Kỹ năng

| Kỹ năng | Phiên bản | Chức năng |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Đối chiếu chéo định danh và số lượt trích dẫn theo từng nguồn; kiểm tra tín hiệu cập nhật hoặc rút bài; định vị toàn văn truy cập mở (OA) và xác minh tệp PDF |
| `skills/literature-analysis` | 1.3.0 | Mười hai quy trình: độ tương đồng chủ đề, trùng lặp văn bản cục bộ, bằng chứng phản biện, hồ sơ tác giả, phản biện mô phỏng, kiểm tra ngụy biện, ma trận tổng quan, gợi ý tạp chí, BibTeX, đọc song ngữ, rà soát khoảng trống nghiên cứu, tái lập kết quả |
| `skills/academic-writing` | 1.1.1 | Biên tập học thuật, hướng dẫn trích dẫn (ISO 690, APA, MLA, Chicago, IEEE, AMA và hồ sơ khu vực), thể lệ tạp chí, dịch vụ kiểm tra tùy chọn, hồ sơ nộp bài và yêu cầu thẩm định khuyết danh của cơ sở đào tạo |
| `skills/math-computation` | 1.2.1 | Định tuyến bài toán theo lĩnh vực và nhiệm vụ với các ví dụ giải tích số và thống kê đã hiệu chỉnh; bốn tệp tham chiếu chuyên sâu |
| `skills/quantitative-paper-audit` | 1.1.0 | Tính toán lại các chỉ số thống kê trong bài báo (độ lớn hiệu ứng, giá trị p, khoảng tin cậy, OR/RR, lực kiểm định thực tế) và phát hiện sai lệch số liệu |
| `skills/research-reproducibility` | 1.0.1 | Quy trình kiểm định khả năng tái lập gồm 14 giai đoạn với bộ kiểm tra quy tắc tái lập có cấu trúc, năm tầng dữ kiện và hồ sơ kiểm định có thể tái lập |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Nhật ký tìm kiếm PRISMA, nhật ký sàng lọc tài liệu, quy đổi độ lớn hiệu ứng, kiểm định tính không đồng nhất, gộp hiệu ứng cố định/ngẫu nhiên, phân tích độ nhạy và chẩn đoán sai lệch xuất bản |
| `skills/literature-watch` | 1.1.0 | Kịch bản theo dõi hàng tuần: giám sát chủ đề, tác giả và công trình trích dẫn DOI mới trên OpenAlex và Crossref; khử trùng lặp và chỉ báo cáo mục mới |
| `skills/retraction-watch` | 1.1.0 | Kịch bản theo dõi hàng tuần: rà soát danh sách DOI cần giám sát đối chiếu với cờ `is_retracted` của OpenAlex và bản ghi cập nhật (`update-to`) của Crossref; chỉ báo cáo khi trạng thái thay đổi |
| `skills/research-object-identity` | 1.1.0 | Định danh tài nguyên nghiên cứu tất định và nguồn gốc / khả năng truy xuất nguồn gốc: chuẩn hóa mã định danh, xác minh 5 trạng thái, đồ thị dẫn xuất định địa chỉ theo nội dung, kiểm tra DAG nhân quả và truy vết ngược dưới 100 ms |
| `skills/claim-evidence-graph` | 1.0.0 | Thiết lập tất định mối quan hệ giữa luận điểm và bằng chứng khoa học, kết nối nhận định học thuật, bản ghi bằng chứng / xác minh và nguồn gốc tính toán |
| `skills/decision-ledger` | 1.0.0 | Nhật ký quyết định nghiên cứu và thử nghiệm thất bại: ghi nhận tuần tự chỉ ghi thêm đối với các lựa chọn học thuật, kết quả âm tính, trạng thái hướng đi / lý do dừng hướng nghiên cứu này và lịch sử hiệu chỉnh kết quả |
| `skills/paper-research` | 1.0.0 | Đọc bài báo và tài liệu bổ sung qua DOI, URL hoặc tệp cục bộ với bước kiểm tra trường thông tin ứng viên, đối chiếu thống kê, lưu trạng thái nghiên cứu bền vững, xuất báo cáo tiếng Trung có dẫn nguồn và so sánh hai bài báo |
| `skills/cross-review-five` | 2.0.0 | Điều phối hội đồng phản biện chéo đa mô hình/tác tử phụ động (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini, v.v.): quy trình thảo luận thưa v2 với thuật toán ghép cặp Hungary Kuhn-Munkres, gom cụm theo luận điểm, chất vấn ẩn danh có mục tiêu và phân loại mức độ nghiêm trọng P0–P3 |

Mười bốn kỹ năng bao gồm tổng cộng 22 tệp tham chiếu Markdown. Các tệp tham chiếu chỉ được nạp khi nhiệm vụ thực sự cần đến.

## Tiêu chuẩn học thuật và đường cơ sở đa hồ sơ

Quy chuẩn trích dẫn, tiêu chí báo cáo và cấu trúc siêu dữ liệu phụ thuộc vào tạp chí mục tiêu, cơ sở nghiên cứu, quỹ tài trợ, ngành học và khu vực pháp lý. Kho lưu trữ thiết lập **ISO 690:2021** (Tài liệu tham khảo thư mục), **ISO 5127:2017** (Từ vựng thông tin và tư liệu) và **W3C PROV** (Mô hình dữ liệu truy xuất nguồn gốc) làm đường cơ sở quốc tế, song hành cùng các hồ sơ khu vực (như GB/T 7714-2025 tại Trung Quốc đại lục, UNE-ISO 690:2024 tại Tây Ban Nha, DIN ISO 690:2021 tại Đức) và tiêu chuẩn chuyên ngành (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Yêu cầu cụ thể của nơi nhận bài luôn được ưu tiên hơn hồ sơ mặc định. Xem thêm [Kiến trúc Tiêu chuẩn Học thuật](../../docs/standards/README.md) và [Hướng dẫn Thuật ngữ Tự nhiên](../../docs/terminology/README.md).

Đợt cập nhật hoàn thiện nhân hệ thống đã xác thực tính nhất quán của DOI/mã định danh, các cờ kết luận định lượng loại trừ lẫn nhau và giao ước chung về các mục cần xác minh lại giữa nhân và biên nhận. Tính toàn vẹn của bộ nhớ đệm được tái tạo trực tiếp từ các gói dữ liệu gốc được lưu giữ và các ràng buộc đã chuẩn hóa, độc lập với danh sách biến đổi trong biên nhận; việc xóa đồng thời một bản ghi trạng thái và khai báo bộ nhớ đệm của nó không thể tạo ra kết quả phát lại hợp lệ giả mạo. Xem chi tiết tại [báo cáo đóng bốn điểm nghẽn](../../docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Tích hợp và sử dụng di động

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
Kho lưu trữ này tuân thủ đặc tả trung lập nhà cung cấp **Agent Plugins v1** (`../../plugin.json`) và cung cấp các công cụ xác minh học thuật cùng tính toán lại thống kê qua **máy chủ MCP** giao thức stdio (`../../mcp.json` / `../../scripts/mcp_server.py`). Tương thích tự nhiên với Claude Code, Cursor, Gemini CLI và mọi khung tác tử hiện đại. (Lưu ý: Dù định danh kho lưu trữ là `academic-research-kernel`, tên khai báo plugin `academic-skills` và các bí danh cấu hình MCP vẫn được giữ cố định để tương thích ngược.)

```bash
# Add as stdio MCP server in your agent harness
uvx academic-research-kernel mcp
```

### 2. Cài đặt gốc trong Hermes
Từ môi trường đã cài đặt Hermes, thực thi:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Cài đặt các kỹ năng còn lại bằng cách thay tên thư mục tương ứng trong định danh đầy đủ. Lệnh tap thông thường đọc nhánh mặc định, nên lần cài đặt mới sẽ nhận bộ kỹ năng liệt kê ở trên. Để kiểm tra một nhánh làm việc trước khi hợp nhất, hãy chuyển sang nhánh đó ở máy cục bộ và làm theo hướng dẫn cài đặt từ thư mục cục bộ của phiên bản Hermes đang dùng. Không mặc định rằng lệnh tap sẽ tự chọn nhánh đang chờ hợp nhất.

Các kỹ năng đi kèm liên quan đã được đối chiếu tại bản chụp thượng nguồn `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video. Hai gói huggingface-hub và llama-cpp nằm trong danh mục tùy chọn và có thể cần cài đặt riêng. ocr-and-documents và pc-hardware-benchmark không có trong bản chụp đó và không phải là phần phụ thuộc. Công cụ phiên làm việc cùng các phụ trợ đọc tài liệu hoặc trình duyệt phụ thuộc vào cấu hình máy cục bộ.

## Truy cập nguồn dữ liệu

- Các truy vấn cơ bản của OpenAlex có thể chạy ẩn danh với hạn mức ngân sách hàng ngày nhỏ. Tài liệu kiểm tra ngày 2026-09-06 quy định hạn mức $0.10/ngày cho truy vấn ẩn danh và $1/ngày khi dùng khóa API miễn phí, cùng trần 100 yêu cầu/giây. Chi phí khác nhau tùy loại truy vấn; đây không phải là quyền truy cập không giới hạn. Lưu khóa tùy chọn vào biến `OPENALEX_API_KEY`, đồng thời sử dụng `per_page` (tối đa 100) và phân trang bằng con trỏ (cursor pagination).
- Crossref cung cấp quyền truy cập siêu dữ liệu công khai có giới hạn tốc độ. Các mối quan hệ cập nhật và tín hiệu Retraction Watch đòi hỏi phải kiểm tra cả DOI lẫn chiều hướng liên kết; việc không tìm thấy bản ghi không chứng minh rằng bài báo chưa bị ảnh hưởng.
- Unpaywall yêu cầu cấu hình địa chỉ email liên hệ thực tế trong biến `UNPAYWALL_EMAIL`. Kết quả trả về không có đường dẫn không đồng nghĩa với việc không tồn tại bản sao truy cập mở.
- arXiv, Europe PMC, PubMed E-utilities và DOAJ là các nguồn bổ trợ với chính sách truy cập riêng; bộ kiểm thử mặc định không gọi toàn bộ các nguồn này. Semantic Scholar áp dụng hạn mức ẩn danh dùng chung và hạn mức khóa API cấp riêng; việc truy cập được API không bảo đảm luôn lấy được ngữ cảnh trích dẫn.
- Scite, Dimensions, Scopus, Web of Science và các sản phẩm phát hiện văn bản AI là những dịch vụ bên ngoài tùy chọn. Cần kiểm tra quyền hạn tài khoản, quyền API và hạn ngạch hiện hành trước khi sử dụng; hệ thống không cam kết có gói miễn phí phổ quát hay mức giá cố định.

Xem thêm [xác thực OpenAlex](https://help.openalex.org/api/authentication/), [ngân sách và chi phí truy vấn](https://help.openalex.org/api/llm-quick-reference/) và [bộ lọc cập nhật Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Tiếp nhận tất định và nhân công khai

Tầng tiếp nhận và phân tích tài liệu nghiên cứu cung cấp `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 bộ chuyển đổi (gồm 14 kỹ năng cùng cơ chế dự phòng dữ liệu thô opaque fallback) và 12 công cụ MCP stdio phi trạng thái. Các biên nhận tiếp nhận được chấp thuận sẽ ràng buộc từng biến đổi ngữ nghĩa được lưu giữ theo phân loại, định danh và mã băm chuẩn SHA-256: đối tượng nghiên cứu, bản ghi CEG, bản ghi nhật ký quyết định, các mục cần xác minh lại, biên nhận vật lý và đăng ký tư liệu. Cơ chế phát lại bộ nhớ đệm kiểm tra các cam kết này độc lập với mã băm bản chụp truyền tải. Nhật ký rỗng vẫn hợp lệ; các lô xử lý nguyên tử nếu thất bại sẽ không để lại trạng thái dở dang.

Quyền truy cập nội dung truy xuất nguồn gốc được cấp tường minh ngoài băng tần (out of band). Các lệnh gọi Python tin cậy truyền `LineageVerificationContext` khi phát lại biên nhận hoặc bản chụp đã tuần tự hóa; các lệnh gọi qua MCP chỉ được phép cung cấp luồng byte nội dung có giới hạn dung lượng, tuyệt đối không được truyền thư mục gốc của hệ thống tệp máy chủ. Ngân sách nội dung mặc định là 10 MiB; máy chủ tin cậy có thể cho phép tư liệu lớn hơn một cách tường minh khi bên tạo và bên kiểm chứng áp dụng cùng chính sách. Nếu thiếu quyền truy cập nội dung, một tuyên bố `fully_verified` sẽ không thể tái lập độc lập và trả về kết quả xác minh không hợp lệ có cấu trúc. Văn bản xuôi chưa cấu trúc được giữ nguyên trạng thái không trong suốt, các ý kiến bất đồng vẫn hiển thị rõ ràng, và nhà nghiên cứu giữ toàn quyền đối với việc chốt trạng thái, dừng hướng đi, mở lại nhánh nghiên cứu, định tuyến và phán đoán tính xác thực.

Xem [tài liệu kiến trúc nhân](../../docs/kernel-architecture.md) để biết chi tiết về giao ước dữ liệu và quy tắc tương thích. Các mốc kiểm tra phân phối và công bố được ghi lại trong [hướng dẫn phát hành](../../docs/distribution-release.md). Bản README tiếng Anh và tiếng Trung giản thể luôn được cập nhật đồng bộ; trạng thái của các bản dịch khác được theo dõi minh bạch trong [bản kê khai đa ngôn ngữ](../../docs/i18n/manifest.json). Định danh bản ứng viên cuối cùng, kết quả CI trên đúng commit HEAD, lịch sử phản biện tích lũy và bằng chứng hợp nhất được lưu tại [hồ sơ nghiệm thu](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Kiểm định (Validation)

Sử dụng một môi trường Python riêng biệt. Các thư viện thời gian chạy phụ thuộc vào từng tác vụ cụ thể và không mặc định có sẵn trong Hermes. Bộ phụ thuộc QA rộng hơn để toàn bộ các ví dụ được đánh dấu đều có thể chạy kiểm tra:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

Trình kiểm tra QA xác thực siêu dữ liệu, tệp tham chiếu, mẫu đường dẫn cá nhân hoặc khóa bí mật đã biết, cú pháp Python và các khối mã thực thi được gắn nhãn. Mỗi ví dụ kiểm thử nhanh (smoke test) chạy nguyên bản trong một tiến trình con mới. Các ví dụ vẽ biểu đồ nhận biến `PLOT_DIR` (mặc định là `~/plots`, được mở rộng đường dẫn tường minh); bộ kiểm thử sử dụng thư mục tạm thời. Các khối mã Python chưa phân loại sẽ bị từ chối; các khối `fragment:` được kiểm tra cú pháp nhưng yêu cầu biến đầu vào định danh nên không chạy độc lập. Các khối `external-test:` chỉ chạy thông qua lệnh kiểm tra API bên ngoài thủ công. Lệnh này trả về 0 khi các kiểm tra đã cấu hình vượt qua, trả về 1 khi lỗi mã nguồn/lược đồ/định danh và trả về 2 khi lỗi kết nối/xác thực/hạn ngạch; các dịch vụ tùy chọn chưa cấu hình sẽ giữ trạng thái SKIP.

Các bài kiểm thử quy chuẩn biên soạn kỹ năng của Hermes (đã ghim phiên bản) được tái sử dụng mà không thay đổi quy tắc riêng của từng kỹ năng. Các bài kiểm tra quần thể toàn bộ bản phân phối thượng nguồn không áp dụng cho tap này; bộ khung kiểm thử tại đây kiểm tra đủ 14 kỹ năng và phân giải tệp tham chiếu đối chiếu với danh mục đi kèm/tùy chọn đã ghim. Đây không phải là bài kiểm tra cài đặt toàn bộ hệ thống Hermes. CI chỉ dùng mạng để cài đặt gói phụ thuộc; các bài kiểm thử thông thường không gọi API học thuật bên ngoài.

Hệ thống CI chạy toàn bộ bộ kiểm thử QA trên Linux x86_64 (Python 3.10–3.14), Linux ARM64 (ubuntu-24.04-arm), bản thử nghiệm Ubuntu 26.04 canary (ubuntu-26.04 và ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest) và macOS Intel (macos-15-intel), kèm theo bước kiểm tra canary trực tiếp với nhánh thượng nguồn. Bản ứng viên cơ sở đã vượt qua 1165 bài kiểm thử cục bộ. Kết quả hiệu chỉnh hiện tại và phạm vi bao phủ được ghi nhận trong [hồ sơ hiệu chỉnh độ chính xác](../../docs/maintenance/correctness-repair-20261008.md); bằng chứng kiểm thử từ xa ghi rõ mã HEAD được kiểm tra. Một quy trình tích hợp tap riêng biệt sẽ chạy khi đẩy mã lên nhánh main: quy trình này cài đặt bản Hermes đã ghim trong `tests/upstream/provenance.json` và thực thi các lệnh `tap add`, `search`, `install` và `list` đối với kho lưu trữ này. Phiên bản chính xác, hạng mục kiểm tra và các giới hạn được trình bày trong [báo cáo kiểm định](../../docs/project-lineage-audit-20260920.md).

Thư mục [tools/longtail/](../../tools/longtail/README.md) chứa bộ sinh nhân tố kịch bản đuôi dài tất định: 4096 tổ hợp ứng viên tạo từ hạt giống SHA256, 30 kịch bản được chọn và một báo cáo độ bao phủ xác minh do máy tính toán. Mô hình v3 thống kê riêng biệt các họ năng lực (E01), 14 kỹ năng thực tế trong kho lưu trữ (E02) và các mục tiêu tác vụ (E03). Mỗi kịch bản gắn với một kỹ năng chính, một mục tiêu tác vụ được hỗ trợ và các năng lực tương thích; mỗi kỹ năng phải xuất hiện ít nhất hai lần dưới hai mục tiêu khác nhau, bao gồm cả mục tiêu cốt lõi đã khai báo. Sự sai lệch giữa thư mục kỹ năng và danh mục nhân tố sẽ làm quá trình xác thực báo lỗi. Giai đoạn mở rộng ngữ nghĩa (chuỗi tác vụ, bộ tiêu chuẩn đối chiếu và tiêm sự kiện thực thi) vẫn là một bước tách biệt; độ bao phủ nhân tố không đồng nghĩa với độ bao phủ thực thi toàn bộ quy trình.

Thư mục `scripts/scfabric/` là tầng thực thi của bộ công cụ tính toán khoa học và thống kê: thăm dò phần cứng, danh mục phụ trợ có cổng kiểm soát kiểu dữ liệu (`dtype`), năm hồ sơ tải công việc, phép đo chuẩn ghép cặp kèm kiểm tra tương đương số học và `ComputeReceipt`. Kết quả đo đạc vòng đầu tiên trên máy thử nghiệm được ghi tại [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md); nguyên tắc vận hành chung là mặc định dùng CPU và chỉ kích hoạt bộ tăng tốc khi có biên nhận xác thực.

## Nghiên cứu bài báo khoa học với Agent cục bộ

Cài đặt `academic-research-kernel[research]==2.1.0` và xuất quy trình làm việc đóng gói sẵn:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Hãy để Work hoặc một Agent cục bộ tương thích đọc tệp `SKILL.md` vừa xuất, sau đó yêu cầu:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Bạn chỉ cần cung cấp mã DOI, liên kết công khai hoặc gói tệp cục bộ. Đối với hai bài báo, hãy yêu cầu Agent so sánh dữ liệu, phương pháp, điều kiện đánh giá và kết quả chính, đồng thời giải thích những phần nào có thể so sánh trực tiếp. Agent sẽ thực hiện xuyên suốt việc đọc văn bản gốc, kiểm tra ứng viên trích xuất, tính toán lại thống kê, tiếp nhận vào nhân, tạo báo cáo và xác minh và kiểm chứng độc lập đối với nguồn dữ liệu trong cùng một nhiệm vụ. Bề mặt giao tiếp MCP hiện có vẫn giữ nguyên 12 công cụ; tầng điều phối mới nằm ở giao diện dòng lệnh CLI và kỹ năng di động.

Các giai đoạn thực thi thực tế của chương trình gồm:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

Lệnh `prepare` thu thập và phân tích tài liệu thành bản kê khai (manifest), mã băm nguồn và các phân đoạn văn bản đã định vị. Lệnh `finish` xác thực dữ liệu trích xuất do Agent tạo ra và tính toán lại các nhận định đủ điều kiện về kiểm định t/p, độ lớn hiệu ứng hai nhóm cũng như số đếm/tỷ lệ phần trăm bằng các hàm thống kê sẵn có, sau đó lưu trạng thái nhân và xuất báo cáo Markdown/HTML tiếng Trung. Lệnh `compare` xác thực đánh giá tường minh của Agent về các điều kiện có thể so sánh. Các lệnh này không nhúng sẵn một mô hình nền chạy ngầm: việc đọc hiểu ngữ nghĩa do chính Agent hiện tại thực hiện theo hướng dẫn của [paper-research](../../skills/paper-research/SKILL.md). Các tệp gốc và bản chụp trích xuất đã lưu hỗ trợ phát lại ngoại tuyến tất định. Việc thu thập dữ liệu qua mạng và lượt đọc ngữ nghĩa mới vẫn được định danh là các thao tác tách biệt.

## Hiệu chỉnh độ chính xác 2.0.1 và xác minh gói phân phối

Bản phát hành sản phẩm 2.0.1 bao gồm các bản sửa lỗi độ chính xác cho tính toán thống kê, theo dõi rút bài và phiên giao tiếp MCP. Công cụ công khai `academic_recompute_statistics` cung cấp tính năng tính lại giá trị p của kiểm định t và chỉ số Cohen's d / Hedges' g cho hai nhóm. Khoảng tin cậy (CI) và tỷ số chênh / tỷ số nguy cơ (OR/RR) được giữ ở tầng hàm Python cấp thấp. Hãy truyền `p_value_literal` (ví dụ `"1.0e-5"`) hoặc `p_value_decimals` khi độ chính xác chữ số thập phân trong báo cáo gốc đóng vai trò quan trọng. Chuỗi nguyên bản giữ lại các chữ số 0 ở cuối; đầu vào kiểu số chỉ giữ biểu diễn giá trị số của nó. Nếu các nguồn chỉ định độ chính xác mâu thuẫn nhau, công cụ sẽ báo lỗi tường minh. Phép so sánh làm tròn nửa lên (round-half-up) bao gồm biên làm tròn dưới và loại trừ biên làm tròn trên. Một sự sai lệch số liệu thống kê thông thường vẫn được ghi nhận là kết quả kiểm tra khoa học thành công; các phép tính không hợp lệ hoặc thất bại một phần sẽ đặt cờ `isError`.

Bước kiểm tra rút bài ghi nhận quan sát hiện tại (`True`/`False`/`unknown`) tách biệt với giá trị đã biết gần nhất (`last-known`). Một cơ chế giữ chỗ ngắn trước truy vấn giúp sắp thứ tự các quan sát trên cùng một DOI và bảo toàn các bản cập nhật của những DOI khác. Quan sát hiện tại và xác nhận lịch sử có số phiên bản riêng: một xác nhận hợp lệ đến muộn có thể cập nhật lịch sử được lưu giữ, trong khi trạng thái `unknown` mới hơn vẫn được đánh dấu rõ là chưa xác minh cho lượt kiểm tra hiện tại. Các dữ liệu mẫu HTTP trong chuỗi kiểm thử hồi quy đều được gắn nhãn là dữ liệu thử nghiệm.

Máy chủ MCP phản hồi lệnh `ping`, giữ im lặng trước các thông báo hợp lệ (bao gồm `notifications/cancelled`) và duy trì phiên giao tiếp stdio hoạt động bình thường sau khi nhận đầu vào không hợp lệ. Bản cài đặt đồng bộ này không quảng bá tính năng hủy lệnh ưu tiên (preemptive cancellation). Việc xử lý thông điệp tuân thủ chặt chẽ [quy ước thông điệp MCP](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) và [đặc tả lệnh ping](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Xây dựng và xác minh các gói phân phối của bản mã nguồn này trong một môi trường cô lập:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

Tùy chọn `--source-checks` giải nén nguyên trạng gói `sdist` ứng viên ra bên ngoài thư mục mã nguồn, đặt biến `ARK_REPO` và `ARK_SDIST` trỏ tới bản ứng viên đó, rồi chạy toàn bộ bài kiểm thử, kiểm tra QA tĩnh, khối mã thực thi và kiểm tra đồng bộ đa ngôn ngữ (i18n). Quá trình cài đặt từ `wheel` và `sdist` đều sử dụng môi trường ảo mới hoàn toàn; `uvx` chạy gói `wheel` cục bộ với bộ nhớ đệm độc lập. Báo cáo đầu ra ghi lại mã băm của từng gói phân phối và đường dẫn nạp mô-đun thực tế sau khi cài đặt. Các tác vụ kiểm tra Hermes định kỳ gọn nhẹ sẽ báo cáo riêng biệt mã SHA được thử nghiệm đối với bản ghim (pinned) và bản mới nhất (latest). Tệp JSON giao ước bên ngoài và bản tóm tắt công việc phân biệt rõ ba trạng thái `healthy`, `degraded` và `failed`; các phép thăm dò bị bỏ qua vẫn được ghi nhận tường minh.

## Tài liệu nghiên cứu và lập kế hoạch

Hai tài liệu dưới đây là tài liệu tham khảo phục vụ lập kế hoạch khám phá, không phải lộ trình cam kết bắt buộc. Các con số thống kê hướng nghiên cứu trong đó được tính toán lại tự động từ cấu trúc phân nhóm lưu tại `docs/direction-primitive-mapping.json`.

- [Tập bản đồ Điểm nghẽn v0 (tiếng Anh)](../../docs/pain-atlas-v0.en.md), [Bản tiếng Trung](../../docs/pain-atlas-v0.zh.md): tổng hợp các điểm nghẽn và lực cản trong suốt vòng đời lao động tri thức học thuật, kèm theo trạng thái xác minh gắn với từng nhận định định lượng.
- [Kế hoạch Nghiên cứu v0 (tiếng Anh)](../../docs/research-plan-v0.en.md), [Bản tiếng Trung](../../docs/research-plan-v0.zh.md): trình bày mô hình Đối tượng Nghiên cứu (Research Object), các lĩnh vực năng lực và năng lực cốt lõi, các hướng nghiên cứu tiềm năng và ma trận phân rã nhân tố giai đoạn một.
