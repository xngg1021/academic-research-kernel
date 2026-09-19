# academic-research-kernel (id)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Inti penelitian akademis netral-harness dan rangkaian musyawarah multi-agen. Menyediakan 13 keahlian akademis dan alat verifikasi dengan titik masuk portabel Agent Plugins v1 dan MCP (Model Context Protocol), serta integrasi bawaan untuk Hermes Agent, Claude Code, Cursor, dan sub-agen CLI kustom. Meliputi verifikasi sumber, analisis literatur, penulisan akademis, komputasi numerik, audit makalah kuantitatif, audit reproduktibilitas, tinjauan sistematis dan meta-analisis, identitas dan silsilah objek penelitian, orkestrasi peninjauan silang antar-model yang dinamis, serta dua otomatisasi pemantauan mingguan. Repositori mencakup pemeriksaan contoh yang dapat dieksekusi; cakupan validasi dan batasan layanan eksternal dicatat dalam [audit](../../docs/audit-20260906.md).

Penulis: Junfu Shi (SJF, xngg1021), Hermes Agent. Penawaran cakupan saat ini: [Source Lineage License 1.0](../../LICENSE).

## Lisensi

Cuplikan yang berisi pemberitahuan ini mengadopsi **Source Lineage License 1.0** untuk Materi Tercakup dan hak yang diidentifikasi dalam [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Komitmen dan pohon SLL pertama, serta komitmen pencatatan batas berikutnya, dibedakan dalam [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) dan [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Cuplikan dari transisi yang dicatat tersebut dan seterusnya yang mempertahankan pemberitahuan ini membawa penawaran tercakup yang sama.

Cuplikan historis hingga `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` dilisensikan di bawah MIT, tunduk pada ketentuan yang berlaku untuk salinan tersebut. Penerima mempertahankan izin MIT yang valid dan tidak perlu bermigrasi ke SLL. [Teks MIT proyek sebelumnya](../../LICENSES/MIT-pre-SLL.txt) tetap dipertahankan; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) dan asal pihak ketiga tetap tidak berubah. Penawaran akar baru tidak menghapus hak-hak tersebut.

SLL secara luas mengizinkan penggunaan, studi, modifikasi, penggunaan komersial, distribusi, dan penambahan kepemilikan, tunduk pada ketentuan lisensi, pemberitahuan, dan silsilah sumber yang berlaku. Ini bukan copyleft dan tidak memerlukan pengungkapan kode sumber. Layanan jaringan murni tanpa menyediakan salinan tidak dengan sendirinya memicu kondisi pemberitahuan silsilah layanan Core. Tidak ada hibah paten tersurat. Teks bahasa Inggris [LICENSE](../../LICENSE) yang tepat mengatur ringkasan informatif ini; `LicenseRef-Source-Lineage-1.0` adalah referensi lokal, bukan penugasan SPDX, dan tidak ada persetujuan OSI yang diklaim. [Penerimaan kontribusi](../../CONTRIBUTING.md) terpisah dari izin lisensi hilir.

## Keahlian

| Keterampilan | Versi | Deskripsi |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Verifikasi silang identitas dan jumlah sitasi; inspeksi pembaruan dan penarikan artikel; pencarian teks OA dan verifikasi identitas PDF |
| `skills/literature-analysis` | 1.3.0 | Dua belas alur kerja: kesamaan topik, tumpang tindih teks, bukti tandingan, profil penulis, simulasi tinjauan, dan pemeriksaan kekeliruan logika |
| `skills/academic-writing` | 1.1.1 | Penulisan dan penyuntingan akademik, panduan sitasi (ISO 690, APA, MLA, Chicago, IEEE, AMA, dan profil regional), serta aturan jurnal |
| `skills/math-computation` | 1.2.1 | Perutean domain matematika dan statistik dengan resep numerik komputasi; berkas referensi lanjutan |
| `skills/quantitative-paper-audit` | 1.1.0 | Penghitungan ulang statistik yang dilaporkan (ukuran efek, nilai p, interval kepercayaan, OR/RR) dan deteksi diskrepansi |
| `skills/research-reproducibility` | 1.0.1 | Jalur audit reproduksibilitas empat belas tahap dengan daftar periksa terstruktur dan catatan yang dapat direproduksi |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Log pencarian PRISMA, log penapisan literatur, konversi ukuran efek, heterogenitas, dan penggabungan meta-analisis |
| `skills/literature-watch` | 1.1.0 | Pemantauan mingguan: pantau topik, penulis, dan sitasi DOI di OpenAlex dan Crossref tanpa duplikasi |
| `skills/retraction-watch` | 1.1.0 | Pemantauan mingguan: periksa ulang daftar pantau DOI terhadap indeks penarikan dan pembaruan OpenAlex serta Crossref |
| `skills/research-object-identity` | 1.1.0 | Identifikasi sumber daya penelitian deterministik dan pelacakan asal-usul dengan validasi DAG kausal |
| `skills/claim-evidence-graph` | 1.0.0 | Penghubung klaim ilmiah dan bukti deterministik yang menghubungkan asersi, catatan bukti, dan asal komputasi |
| `skills/decision-ledger` | 1.0.0 | Log Keputusan Penelitian: log deterministik khusus penambahan untuk keputusan, hasil negatif, dan status rute penelitian |
| `skills/cross-review-five` | 2.0.0 | Orkestrasi panel multi-peninjau dinamis untuk model heterogen dengan penugasan Kuhn-Munkres dan musyawarah jarang v2 |

Terdapat 21 berkas referensi Markdown di tiga belas keahlian. Referensi hanya dimuat saat dibutuhkan.

## Standar Akademik dan Garis Dasar Multi-Profil

Gaya sitasi, kriteria pelaporan, dan kontrak metadata bergantung pada jurnal target, institusi, penyandang dana, disiplin, dan yurisdiksi. Repositori ini menetapkan **ISO 690:2021** (Referensi bibliografi), **ISO 5127:2017** (Kosakata informasi dan dokumentasi), dan **W3C PROV** (Model data silsilah) sebagai garis dasar internasional, bersama profil regional dan standar disiplin (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Persyaratan tempat target lebih diutamakan daripada profil default. Lihat [Arsitektur Standar Akademik](../../docs/standards/README.md) dan [Panduan Terminologi Alami](../../docs/terminology/README.md).

## Integrasi dan Penggunaan Portabel

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
Repositori ini mematuhi spesifikasi netral vendor **Agent Plugins v1** (`../../plugin.json`) dan mengekspos alat verifikasi akademik inti dan penghitungan ulang statistik melalui **server MCP** stdio (`../../mcp.json` / `python scripts/mcp_server.py`). Kompatibel dengan Claude Code, Cursor, Gemini CLI, dan kerangka kerja agen modern apa pun.

```bash
# Add as stdio MCP server in your agent harness
python scripts/mcp_server.py
```

### 2. Instalasi Asli di Hermes
Dari instalasi Hermes, jalankan:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Instal yang lain dengan mengganti nama direktori pada pengidentifikasi lengkap. Tap biasa membaca cabang default. Keahlian terkait yang dipaketkan diperiksa pada komit `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video.

## Akses Sumber Data

- Kueri dasar OpenAlex dapat berjalan secara anonim dengan anggaran harian kecil ($0.10/hari anonim dan $1/hari dengan kunci API gratis, batas 100 permintaan/detik). Simpan kunci opsional di `OPENALEX_API_KEY`.
- Crossref menyediakan akses metadata publik dengan pembatasan kecepatan. Sinyal pembaruan dan Retraction Watch memerlukan pemeriksaan DOI.
- Unpaywall memerlukan email kontak nyata di `UNPAYWALL_EMAIL`.
- arXiv, Europe PMC, PubMed, dan DOAJ adalah sumber pelengkap dengan kebijakan mereka sendiri. Scite, Dimensions, Scopus, dan Web of Science adalah layanan eksternal opsional.

## Validasi

Gunakan lingkungan Python khusus. Ketergantungan QA mencakup semua pemeriksaan yang dapat dieksekusi:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA memvalidasi metadata, referensi, pola jalur pribadi/rahasia yang diketahui, sintaksis Python, dan blok kode yang ditandai. Mengembalikan 0 jika berhasil, 1 jika gagal kode/skema/identitas, dan 2 jika transportasi/autentikasi/kuota tidak tersedia.

CI menjalankan rangkaian pengujian lengkap di Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview, Windows x86_64, Windows ARM64, macOS ARM64, dan macOS Intel, dengan 632 pengujian unit yang lulus dan 40 blok kode yang dapat dieksekusi divalidasi.

tools/longtail/ menyimpan generator skenario ekstrim long-tail deterministik: 4096 kombinasi kandidat dengan benih SHA256 pada sumbu faktor terpisah, pemilihan cakupan serakah, dan laporan cakupan di generated-scenarios.json.

scripts/scfabric/ adalah fabric komputasi ilmiah: penyelidikan perangkat keras, katalog backend dengan filter tipe data, lima profil beban kerja, dan ComputeReceipt. Pengukuran tercatat dalam [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md).

## Dokumen Penelitian dan Perencanaan

Dokumen-dokumen ini adalah referensi perencanaan eksploratif, bukan peta jalan yang mengikat.

- [Atlas Titik Masalah v0 (Inggris)](../../docs/pain-atlas-v0.en.md), [Versi Bahasa Mandarin](../../docs/pain-atlas-v0.zh.md): Titik gesekan dalam siklus kerja pengetahuan akademik dengan status verifikasi.
- [Rencana Penelitian v0 (Inggris)](../../docs/research-plan-v0.en.md), [Versi Bahasa Mandarin](../../docs/research-plan-v0.zh.md): Model Research Object, area kemampuan inti, dan matriks dekomposisi faktor.
