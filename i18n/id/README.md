# academic-research-kernel (id)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Inti pengelolaan status penelitian ilmiah dan verifikasi metodologis yang deterministik untuk alur kerja riset berbantuan agen, independen dari lingkungan eksekusi tertentu. Sistem ini menyatukan identitas objek penelitian, catatan bukti / verifikasi empiris, hubungan klaim dan bukti (CEG), serta catatan keputusan penelitian dan kegagalan yang bersifat tambah-saja melalui mekanisme ingesti artefak penelitian dan server Model Context Protocol (MCP) universal. Empat belas keahlian akademik khusus bertindak sebagai penghasil sekaligus pengguna status penelitian terverifikasi, dengan dukungan bawaan untuk Claude Code, Cursor, Codex, Gemini CLI, dan Hermes Agent. Cakupan validasi serta batasan layanan eksternal didokumentasikan dalam [laporan audit](../../docs/project-lineage-audit-20260920.md).

Penulis: Junfu Shi (SJF, xngg1021), Hermes Agent. Penawaran lisensi saat ini: [Source Lineage License 1.0](../../LICENSE).

## Mulai cepat

Jalankan versi 2.1.0 menggunakan [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx academic-research-kernel@2.1.0 mcp
```

Catatan [rilis 2.1.0](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0) memuat hash distribusi dan status publikasi. Paket wheel rilis juga dapat dijalankan secara lokal dengan `uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`. Python 3.10–3.14 didukung penuh; opsi `uvx --python 3.12` secara eksplisit memilih interpreter yang kompatibel. Seluruh 12 alat deterministik, termasuk modul perhitungan statistik, sudah tercakup dalam instalasi dasar.

## Verifikasi instalasi

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

Diagnostik luring memeriksa dependensi, skema data, serta definisi ke-12 alat. Layanan eksternal opsional dapat dibiarkan tanpa konfigurasi. Gunakan `doctor --json` untuk menghasilkan keluaran yang dapat dibaca mesin.

## Instalasi paket

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Sebagai alternatif, instal menggunakan `pipx install academic-research-kernel==2.1.0` atau `python -m pip install academic-research-kernel==2.1.0` di dalam lingkungan virtual yang didukung. Ekstra `[full]` menambahkan pustaka untuk contoh komputasi ilmiah lanjutan; `[qa]` menyertakan perangkat validasi repositori termasuk pengurai PDF. Ekstra `[research]` menambahkan `pypdf==6.19.0` dan `fonttools==4.65.0` agar pengodean font PDF konsisten pada instalasi bersih, keduanya kompatibel dengan Python 3.10. Pembacaan HTML/XML terstruktur serta pembacaan DOCX/XLSX berbatas ukuran menggunakan pustaka standar Python. Backend GPU dan layanan berbayar tetap bersifat opsional.

## Hermes

Pastikan `uv` tersedia pada `PATH` proses Hermes, lalu instal dan aktifkan plugin portabel secara eksplisit:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

Identitas `academic-skills` tetap dipertahankan demi kompatibilitas mundur, mencakup 14 keahlian termasuk `paper-research`. Berkas `mcp.json` pada plugin memanggil `uv run --frozen --no-dev --no-editable` dengan Python 3.12 dan `uv.lock` dari repositori, serta menempatkan lingkungan terisolasinya di `${PLUGIN_DATA}/runtime`. Pada penggunaan pertama, dependensi dipasang secara mandiri tanpa meminjam paket Python milik Hermes maupun sistem operasi; akses jaringan diperlukan saat penggunaan perdana untuk mengunduh paket atau interpreter yang belum tersedia. Metode tap lama yang hanya memasang keahlian tetap didukung sebagaimana dijelaskan pada bagian integrasi portabel di bawah.

## Menjalankan dari kode sumber

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Lihat [panduan distribusi dan rilis](../../docs/distribution-release.md) untuk klasifikasi dependensi, reproduksi paket, identitas rilis, titik pemeriksaan publikasi, dan cakupan validasi.

## Lisensi

Cuplikan repositori yang memuat pemberitahuan ini mengadopsi **Source Lineage License 1.0** untuk Materi Tercakup beserta hak-hak yang diuraikan dalam [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Komit dan pohon objek SLL pertama, serta komit pencatatan batas sesudahnya, dibedakan secara jelas dalam [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) dan [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Cuplikan setelah transisi tercatat tersebut yang tetap mempertahankan pemberitahuan ini membawa penawaran lisensi dengan cakupan yang sama.

Cuplikan historis hingga `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` dilisensikan di bawah MIT sesuai ketentuan yang berlaku pada salinan tersebut. Penerima tetap memiliki izin MIT yang sah dan tidak diwajibkan beralih ke SLL. [Teks lisensi MIT proyek sebelumnya](../../LICENSES/MIT-pre-SLL.txt) tetap disimpan; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) beserta asal-usul pihak ketiganya tidak berubah. Penawaran lisensi baru di tingkat akar tidak menghapus hak-hak terdahulu tersebut.

SLL secara luas mengizinkan penggunaan, pembelajaran, modifikasi, pemanfaatan komersial, distribusi, dan penambahan komponen kepemilikan, dengan tunduk pada ketentuan lisensi, pemberitahuan, dan silsilah kode sumber yang berlaku. Lisensi ini bukan copyleft dan tidak menuntut pembukaan kode sumber. Penyediaan layanan jaringan murni tanpa menyerahkan salinan tidak dengan sendirinya memicu kewajiban pemberitahuan silsilah layanan Core. Tidak ada pemberian hak paten secara tersurat, dan materi pihak ketiga tetap berada di bawah ketentuannya masing-masing. Teks bahasa Inggris asli pada [LICENSE](../../LICENSE) menjadi acuan utama atas ringkasan informatif ini; `LicenseRef-Source-Lineage-1.0` merupakan referensi lokal, bukan pengenal resmi SPDX, dan tidak ada klaim persetujuan OSI. Kebijakan [penerimaan kontribusi](../../CONTRIBUTING.md) terpisah dari izin lisensi bagi pengguna hilir.

## Keahlian

| Keahlian | Versi | Fungsi utama |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Memeriksa silang identitas publikasi dan jumlah sitasi spesifik per sumber; memeriksa sinyal pembaruan atau penarikan artikel; menemukan naskah Open Access dan memverifikasi keaslian PDF |
| `skills/literature-analysis` | 1.3.0 | Dua belas alur kerja analisis: kemiripan topik, tumpang tindih teks lokal, bukti tandingan, profil penulis, simulasi telaah sejawat, pemeriksaan sesat pikir, matriks tinjauan, kandidat jurnal, BibTeX, pembacaan dwibahasa, pemetaan celah riset, dan reproduksi |
| `skills/academic-writing` | 1.1.1 | Penyuntingan naskah ilmiah, panduan gaya sitasi (ISO 690, APA, MLA, Chicago, IEEE, AMA, dan profil regional), petunjuk penulis jurnal, layanan deteksi opsional, berkas pengajuan naskah, dan persyaratan institusional |
| `skills/math-computation` | 1.2.1 | Perutean domain dan tugas komputasi dengan contoh numerik serta statistik yang telah dikoreksi; empat berkas referensi lanjutan per bidang |
| `skills/quantitative-paper-audit` | 1.1.0 | Menghitung ulang statistik yang dilaporkan dalam makalah (ukuran efek, nilai p, interval kepercayaan, OR/RR, daya statistik tercapai) dan mendeteksi ketidaksesuaian angka |
| `skills/research-reproducibility` | 1.0.1 | Alur audit reproduktibilitas empat belas tahap dengan daftar periksa terstruktur, lima tingkatan verifikasi fakta, dan catatan audit yang dapat direproduksi |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Log pencarian PRISMA, catatan penapisan literatur, konversi ukuran efek, analisis heterogenitas, penggabungan efek tetap maupun acak, analisis sensitivitas, dan diagnostik bias publikasi |
| `skills/literature-watch` | 1.1.0 | Pemantauan mingguan: melacak topik, penulis, dan karya pengutip DOI di OpenAlex serta Crossref; menghapus duplikat dan hanya melaporkan publikasi baru |
| `skills/retraction-watch` | 1.1.0 | Pemantauan mingguan: memeriksa ulang daftar pantau DOI terhadap status `is_retracted` di OpenAlex dan catatan pembaruan Crossref (sinyal `update-to`); hanya melaporkan perubahan status |
| `skills/research-object-identity` | 1.1.0 | Identifikasi sumber daya riset deterministik dan asal-usul / ketertelusuran artefak: normalisasi pengenal, verifikasi 5 status, graf turunan beralamat konten, validasi DAG kausal, dan pelacakan silsilah di bawah 100 md |
| `skills/claim-evidence-graph` | 1.0.0 | Penautan deterministik hubungan klaim dan bukti yang menghubungkan pernyataan ilmiah, catatan bukti empiris, dan asal-usul komputasi |
| `skills/decision-ledger` | 1.0.0 | Catatan keputusan penelitian dan kegagalan: log deterministik tambah-saja untuk pilihan metodologis, hasil negatif, status rute / alasan rute dihentikan, dan revisi kesimpulan |
| `skills/paper-research` | 1.0.0 | Pembacaan makalah dan suplemen melalui DOI, URL, atau berkas lokal disertai validasi kandidat bidang, pemeriksaan statistik, penyimpanan status riset persisten, laporan bahasa Mandarin tertaut sumber, serta perbandingan dua makalah |
| `skills/cross-review-five` | 2.0.0 | Orkestrasi panel multi-peninjau dinamis yang mendukung beragam model dan sub-agen (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini, dll.): alur Sparse Deliberation v2 dengan penugasan Kuhn-Munkres Hungarian, pengelompokan tingkat asersi, sanggahan anonim terarah, dan pemeringkatan tingkat keparahan P0–P3 |

Terdapat 22 berkas referensi Markdown yang tersebar di keempat belas keahlian tersebut. Berkas referensi hanya dimuat ketika diperlukan.

## Standar Akademik dan Garis Dasar Multi-Profil

Gaya sitasi, kriteria pelaporan ilmiah, dan kontrak metadata bergantung pada jurnal tujuan, institusi, lembaga pendanaan, disiplin ilmu, serta yurisdiksi. Repositori ini menetapkan **ISO 690:2021** (Referensi bibliografi), **ISO 5127:2017** (Kosakata informasi dan dokumentasi), serta **W3C PROV** (Model data asal-usul) sebagai acuan dasar internasional, berdampingan dengan profil regional (seperti GB/T 7714-2025 di Tiongkok Daratan, UNE-ISO 690:2024 di Spanyol, DIN ISO 690:2021 di Jerman) dan standar disiplin ilmu (APA edisi ke-7, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Ketentuan spesifik dari jurnal atau tempat publikasi tujuan selalu diutamakan di atas profil bawaan. Lihat [Arsitektur Standar Akademik](../../docs/standards/README.md) dan [Panduan Terminologi Alami](../../docs/terminology/README.md).

Perbaikan integritas akhir memvalidasi koherensi antara DOI dan pengenal eksternal, sifat saling lepas pada penanda boolean putusan kuantitatif, serta kontrak bersama untuk hal-hal yang perlu ditinjau antara inti sistem dan tanda terima ingesti. Kelengkapan tembolok (cache) direkonstruksi dari amplop sumber yang disimpan dan ikatan ternormalisasi secara independen dari daftar mutasi pada tanda terima; menghapus catatan sekaligus deklarasi temboloknya tidak akan menghasilkan pemutaran ulang yang diterima. Lihat [rangkuman penyelesaian empat kendala utama](../../docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Integrasi dan Penggunaan Portabel

### 1. Universal Agent Plugins v1 dan Model Context Protocol (MCP)
Repositori ini mematuhi spesifikasi netral-vendor **Agent Plugins v1** (`../../plugin.json`) serta menyediakan alat verifikasi bibliografi dan penghitungan ulang statistik melalui **server MCP** berbasis stdio (`../../mcp.json` / `../../scripts/mcp_server.py`). Kompatibel dengan Claude Code, Cursor, Gemini CLI, dan berbagai kerangka kerja agen modern. Meskipun identitas repositori adalah `academic-research-kernel`, nama manifes plugin `academic-skills` dan alias konfigurasi MCP tetap dipertahankan demi kompatibilitas mundur.

```bash
# Add as stdio MCP server in your agent harness
uvx academic-research-kernel mcp
```

### 2. Instalasi Bawaan di Hermes
Dari lingkungan instalasi Hermes:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Instal keahlian lainnya dengan mengganti nama direktori pada pengidentifikasi lengkap. Perintah tap standar membaca cabang utama repositori sehingga memasang rangkaian keahlian di atas. Untuk memeriksa cabang kerja sebelum penggabungan, lakukan checkout cabang tersebut secara lokal dan ikuti petunjuk instalasi folder lokal sesuai versi Hermes yang terpasang; jangan berasumsi bahwa perintah tap memilih cabang pengajuan perubahan.

Keahlian terkait yang telah diperiksa terhadap cuplikan upstream `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, dan manim-video. Paket huggingface-hub serta llama-cpp berada di katalog opsional dan mungkin memerlukan instalasi terpisah. Adapun ocr-and-documents dan pc-hardware-benchmark tidak ditemukan pada cuplikan tersebut dan bukan merupakan dependensi. Alat sesi serta backend dokumen atau peramban bergantung pada konfigurasi lokal.

## Akses Sumber Data

- Kueri dasar OpenAlex dapat dijalankan secara anonim dengan anggaran harian terbatas. Berdasarkan dokumentasi yang diperiksa pada 2026-09-06, kuota harian adalah US$0,10/hari untuk akses anonim dan US$1/hari dengan kunci API gratis, disertai batas kecepatan 100 permintaan/detik. Biaya berbeda menurut jenis kueri dan bukan berupa akses tanpa batas. Simpan kunci opsional dalam variabel `OPENALEX_API_KEY`, serta gunakan parameter `per_page` (maksimum 100) dan paginasi kursor.
- Crossref menyediakan akses metadata publik dengan pembatasan laju permintaan. Hubungan pembaruan dan sinyal Retraction Watch memerlukan pemeriksaan DOI serta arah tautan; tidak adanya catatan tidak membuktikan bahwa sebuah makalah bebas dari koreksi atau penarikan.
- Unpaywall mewajibkan alamat email kontak yang valid pada `UNPAYWALL_EMAIL`. Tidak ditemukannya lokasi tautan bukan bukti bahwa salinan Open Access tidak tersedia.
- arXiv, Europe PMC, PubMed E-utilities, dan DOAJ merupakan sumber pelengkap dengan kebijakan masing-masing dan tidak semuanya dijalankan oleh pengujian bawaan. Semantic Scholar menerapkan batas anonim bersama serta kuota kunci API terpisah; ketersediaan akses tidak menjamin tersedianya konteks sitasi.
- Scite, Dimensions, Scopus, Web of Science, dan layanan deteksi teks AI merupakan layanan eksternal opsional. Periksa hak akses akun, izin API, dan kuota terkini sebelum digunakan; tidak ada jaminan paket gratis universal maupun harga tetap.

Lihat panduan [autentikasi OpenAlex](https://help.openalex.org/api/authentication/), [anggaran dan biaya kueri](https://help.openalex.org/api/llm-quick-reference/), serta [filter pembaruan Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Ingesti deterministik dan inti publik

Antarmuka ingesti artefak penelitian menyediakan `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 adaptor (14 keahlian ditambah fallback buram `opaque fallback`), serta 12 alat stdio MCP tanpa status (stateless). Tanda terima ingesti yang disetujui mengikat setiap mutasi semantik yang disimpan berdasarkan jenis, identitas, dan digest SHA-256 kanonis: objek riset, catatan hubungan klaim dan bukti (CEG), entri catatan keputusan penelitian dan kegagalan, hal-hal yang perlu ditinjau, bukti fisik, serta registrasi artefak. Pemutaran ulang tembolok memverifikasi komitmen tersebut secara independen dari hash cuplikan transpor. Catatan kosong tetap valid, dan kelompok operasi atomik yang gagal tidak meninggalkan perubahan status parsial.

Otoritas konten silsilah bersifat eksplisit dan dikirimkan di luar jalur utama. Pemanggil Python tepercaya meneruskan `LineageVerificationContext` saat memutar ulang tanda terima atau cuplikan terserialisasi; pemanggil MCP dapat mengirimkan byte konten secara terbatas, namun tidak pernah mengirimkan akar sistem berkas host. Anggaran konten bawaan adalah 10 MiB, dan host tepercaya dapat secara eksplisit mengizinkan artefak berukuran lebih besar di bawah kebijakan produsen dan pemeriksa yang sama. Tanpa otoritas konten, klaim berstatus `fully_verified` tidak dapat direproduksi secara mandiri dan menghasilkan keluaran verifikasi tidak valid yang terstruktur. Teks bebas tetap diperlakukan buram, perbedaan pendapat tetap ditampilkan, dan peneliti memegang kendali penuh atas komit, penghentian atau pembukaan kembali rute, perutean, serta penilaian kebenaran ilmiah.

Lihat [arsitektur inti](../../docs/kernel-architecture.md) untuk rincian kontrak dan aturan kompatibilitas. Titik pemeriksaan distribusi dan publikasi dicatat dalam [panduan rilis](../../docs/distribution-release.md). README bahasa Inggris dan bahasa Mandarin Sederhana selalu disinkronkan secara langsung, sedangkan status terjemahan bahasa lainnya dicatat secara eksplisit di dalam [manifes sinkronisasi](../../docs/i18n/manifest.json). Identitas kandidat akhir, hasil CI pada komit terkait, serta bukti tinjauan kumulatif terdokumentasi pada [catatan penutupan](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Validasi

Gunakan lingkungan Python khusus. Pustaka waktu jalan bergantung pada tugas spesifik dan tidak dijamin telah terpasang di Hermes. Dependensi QA mencakup paket yang lebih luas agar seluruh contoh berpenanda dapat dijalankan:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

Skrip QA memvalidasi metadata, tautan referensi lokal, pola jalur pribadi atau rahasia yang dikenal, sintaksis Python, dan blok kode dapat dieksekusi yang memiliki penanda. Setiap contoh `smoke` dijalankan tanpa perubahan di dalam subproses baru. Contoh pembuatan grafik menerima variabel `PLOT_DIR` (bawaan `~/plots`, diekspansi secara eksplisit) dan menggunakan direktori sementara selama pengujian. Blok kode Python tanpa klasifikasi akan ditolak; blok `fragment:` diperiksa sintaksisnya tetapi memerlukan masukan bernama dan tidak dijalankan secara mandiri. Blok `external-test:` hanya dijalankan melalui perintah verifikasi eksternal manual, yang mengembalikan kode `0` apabila pemeriksaan yang dikonfigurasi lulus, `1` untuk kegagalan kode, skema, atau identitas, dan `2` apabila jaringan, autentikasi, atau kuota tidak tersedia, sementara layanan opsional yang belum dikonfigurasi tetap berstatus `SKIP`.

Pengujian penulisan keahlian Hermes yang dipatok digunakan kembali tanpa mengubah aturan per keahliannya. Pemeriksaan populasi distribusi penuh di repositori hulu tidak berlaku untuk repositori ini; rangkaian pengujian kami memeriksa keempat belas keahlian dan mengurai referensi terhadap katalog bawaan maupun opsional yang dipatok. Ini bukan pengujian instalasi Hermes secara menyeluruh. Lingkungan CI menggunakan jaringan hanya saat memasang dependensi, dan pengujian perubahan reguler tidak memanggil API akademik eksternal.

CI menjalankan rangkaian QA lengkap di Linux x86_64 (Python 3.10–3.14), Linux ARM64 (`ubuntu-24.04-arm`), Ubuntu 26.04 preview canary (`ubuntu-26.04` dan `ubuntu-26.04-arm`), Windows x86_64, Windows ARM64 (`windows-11-arm`), macOS ARM64 (`macos-latest`), dan macOS Intel (`macos-15-intel`), disertai validasi canary langsung terhadap repositori hulu. Kandidat dasar historis telah meluluskan 1165 pengujian lokal. Hasil perbaikan terkini dan batas cakupan dicatat dalam [laporan perbaikan ketepatan](../../docs/maintenance/correctness-repair-20261008.md), sedangkan bukti jarak jauh mencantumkan komit `HEAD` yang diuji secara terpisah. Alur kerja integrasi tap terpisah berjalan setiap ada dorongan ke cabang `main`: alur ini memasang kode Hermes terpaku yang tercatat di `tests/upstream/provenance.json` lalu menguji perintah `tap add`, `search`, `install`, dan `list` terhadap repositori ini. Versi tepat, daftar pemeriksaan, dan batasan diuraikan dalam [laporan audit](../../docs/project-lineage-audit-20260920.md).

Direktori [tools/longtail/](../../tools/longtail/README.md) menyimpan generator faktor ekor panjang deterministik: 4096 kandidat berbenih SHA-256, 30 skenario terpilih, dan laporan cakupan verifikasi yang dihitung mesin. Model v3 menghitung secara terpisah keluarga kapabilitas (E01), 14 keahlian aktual di repositori (E02), serta tujuan tugas (E03). Setiap skenario memiliki satu keahlian utama, satu tujuan tugas yang didukung, dan kapabilitas yang kompatibel; setiap keahlian wajib muncul minimal dua kali di bawah dua tujuan berbeda, termasuk tujuan inti yang dideklarasikannya. Ketidaksesuaian direktori keahlian akan menggagalkan validasi. Perluasan semantik (rantai tugas, oracle pengujian, dan injeksi kejadian terekseskusi) tetap menjadi tahap terpisah; cakupan faktor tidak membuktikan cakupan eksekusi alur kerja secara utuh.

Direktori `scripts/scfabric/` berisi perangkat alat komputasi ilmiah dan statistik: pemeriksa perangkat keras, katalog backend dengan gerbang tipe data (`dtype`), lima profil beban kerja, tolok ukur berpasangan dengan penerimaan kesetaraan numerik, serta `ComputeReceipt`. Hasil pengukuran tahap pertama di mesin ini terdokumentasi dalam [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md); aturan praktisnya adalah menggunakan CPU secara bawaan dan hanya mengaktifkan akselerator jika disertai tanda terima komputasi.

## Meneliti makalah dengan Agen lokal

Instal `academic-research-kernel[research]==2.1.0` dan ekspor alur kerja terpaket:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Minta Work atau Agen lokal yang kompatibel untuk membaca berkas `SKILL.md` yang telah diekspor tersebut, kemudian berikan instruksi:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Cukup berikan DOI, tautan publik, atau bundel berkas lokal. Untuk dua makalah, minta Agen membandingkan data, metode, kondisi evaluasi, dan hasil, sembari menjelaskan bagian mana yang dapat dibandingkan secara langsung. Agen akan melanjutkan pembacaan naskah asli, validasi kandidat bidang, penghitungan ulang, ingesti ke inti sistem, pembuatan laporan, hingga peninjauan sumber independen dalam satu tugas yang sama. Permukaan MCP yang ada tetap mempertahankan 12 alatnya, sedangkan orkestrasi baru berjalan melalui CLI dan keahlian portabel.

Tahapan program yang sebenarnya adalah:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

Perintah `prepare` mengambil dan mengurai materi menjadi manifes, hash sumber, serta segmen teks yang terlokalisasi. Perintah `finish` memvalidasi hasil ekstraksi buatan Agen dan menghitung ulang klaim uji-t/nilai p, ukuran efek dua kelompok, serta hitungan atau persentase yang memenuhi syarat menggunakan alat statistik yang tersedia, lalu menyimpan status inti beserta laporan bahasa Mandarin dalam format Markdown dan HTML. Perintah `compare` memvalidasi penilaian eksplisit Agen mengenai kondisi yang sebanding antarstudi. Perintah-perintah ini tidak menanamkan model bahasa residen tersendiri: pembacaan semantik dilakukan oleh Agen aktif mengikuti panduan [paper-research](../../skills/paper-research/SKILL.md). Berkas asli dan cuplikan ekstraksi yang tersimpan mendukung pemutaran ulang luring secara deterministik, sementara pengambilan jaringan dan pembacaan semantik baru tetap dicatat sebagai operasi terpisah.

## Perbaikan ketepatan 2.0.1 dan verifikasi distribusi

Rilis produk 2.0.1 mencakup perbaikan ketepatan perhitungan statistik dan penanganan protokol. Alat publik `academic_recompute_statistics` menyediakan nilai p uji-t serta ukuran efek `d` Cohen / `g` Hedges dua kelompok, sementara interval kepercayaan dan `OR/RR` tetap berupa fungsi Python tingkat bawah. Berikan parameter `p_value_literal` (misalnya `"1.0e-5"`) atau `p_value_decimals` apabila presisi angka pada laporan makalah bersifat penting. Nilai literal mempertahankan angka nol di belakang koma, sedangkan masukan numerik biasa hanya menyimpan representasi numeriknya; sumber presisi yang saling bertentangan akan digagalkan secara eksplisit. Perbandingan pembulatan (`round-half-up`) menyertakan batas bawah pembulatan dan mengecualikan batas atas. Ketidaksesuaian angka biasa merupakan hasil temuan ilmiah yang sah, sedangkan perhitungan yang tidak valid atau gagal sebagian akan menetapkan penanda `isError`.

Pemeriksaan penarikan artikel (retraksi) mencatat pengamatan saat ini (`True`/`False`/`unknown`) secara terpisah dari nilai terakhir yang diketahui. Reservasi singkat sebelum kueri mengurutkan pengamatan pada DOI yang sama dan menjaga pembaruan DOI lainnya. Pengamatan saat ini dan konfirmasi historis memiliki versi terpisah: konfirmasi yang datang terlambat dapat memperbarui riwayat yang disimpan, sementara status `unknown` yang lebih baru tetap ditandai secara eksplisit sebagai belum terverifikasi untuk pemeriksaan berjalan. Respons HTTP tiruan dalam rantai pengujian regresi diberi label sebagai data uji.

Server MCP merespons `ping`, tetap diam terhadap notifikasi yang valid (termasuk `notifications/cancelled`), dan menjaga sesi stdio tetap hidup setelah menerima masukan yang tidak valid. Implementasi sinkron tidak mendeklarasikan pembatalan preemptif. Penanganan pesan mengikuti [kontrak pesan MCP](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) dan [spesifikasi ping](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Bangun dan verifikasi paket distribusi dari salinan kerja ini menggunakan lingkungan terisolasi:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

Opsi `--source-checks` mengekstrak kandidat `sdist` tanpa perubahan di luar direktori repositori, mengatur `ARK_REPO` dan `ARK_SDIST` ke kandidat tersebut, lalu menjalankan pengujian unit, QA statis, blok kode dapat dieksekusi, dan pemeriksaan sinkronisasi i18n. Instalasi `wheel` dan `sdist` masing-masing menggunakan lingkungan baru yang bersih, sedangkan `uvx` memakai berkas `wheel` lokal dengan tembolok terpisah. Laporan akhir mencatat hash artefak dan jalur impor terpasang. Pemeriksaan berkala ringan Hermes (`pinned` dan `latest`) melaporkan SHA yang diuji secara mandiri. JSON kontrak eksternal dan ringkasan pekerjaan menggunakan status `healthy`, `degraded`, dan `failed`, dengan pengujian yang dilewati tetap dicatat secara eksplisit.

## Dokumen penelitian dan perencanaan

Kedua dokumen berikut merupakan referensi perencanaan eksploratif, bukan peta jalan yang mengikat. Nomor arah penelitian di dalamnya dihitung ulang dari pengelompokan yang disimpan pada `docs/direction-primitive-mapping.json`.

- [Pain Atlas v0 (Inggris)](../../docs/pain-atlas-v0.en.md), [中文版](../../docs/pain-atlas-v0.zh.md): titik-titik hambatan di sepanjang siklus kerja pengetahuan akademik, dilengkapi status verifikasi pada setiap klaim kuantitatif.
- [Research Plan v0 (Inggris)](../../docs/research-plan-v0.en.md), [中文版](../../docs/research-plan-v0.zh.md): model Research Object, bidang kapabilitas inti, kandidat arah riset, dan matriks dekomposisi faktor tahap pertama.
