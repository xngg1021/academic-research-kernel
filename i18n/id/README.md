# academic-research-kernel (id)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Kernel netral untuk penelitian akademik dan rangkaian musyawarah multi-agen. Menyediakan 13 keterampilan akademik dan alat verifikasi dengan titik masuk portabel Agent Plugins v1 dan MCP (Model Context Protocol), serta integrasi bawaan untuk Hermes Agent, Claude Code, Cursor, dan sub-agen CLI.

Penulis: Junfu Shi (SJF, xngg1021), Hermes Agent. Lisensi: [Source Lineage License 1.0](../../LICENSE).

## Lisensi

Repositori ini mengadopsi **Source Lineage License 1.0** untuk materi yang dicakup dalam [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Komit historis hingga `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` tetap berada di bawah lisensi MIT.

## Keterampilan

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

## Standar Akademik dan Profil Multi-Wilayah

Repositori ini menetapkan **ISO 690:2021** (Referensi bibliografi), **ISO 5127:2017** (Fondasi dan kosakata) serta **W3C PROV** (Model data asal-usul) sebagai landasan internasional, bersama profil regional dan standar disiplin ilmu (APA 7th, IEEE, PRISMA 2020, ICMJE). Lihat [Arsitektur Standar](../../docs/standards/README.md) dan [Panduan Terminologi](../../docs/terminology/README.md).

## Integrasi dan Penggunaan Portabel

```bash
python scripts/mcp_server.py
```

## Validasi dan CI

CI menjalankan rangkaian uji QA lengkap di Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64, dan macOS Intel, dengan 625 uji unit lolos dan validasi canary hulu langsung.

## Dokumen Penelitian dan Perencanaan

- [Atlas Titik Masalah v0 (Inggris)](../../docs/pain-atlas-v0.en.md), [Versi Bahasa Mandarin](../../docs/pain-atlas-v0.zh.md): Titik gesekan dalam siklus kerja akademik dengan status verifikasi bukti.
- [Rencana Penelitian v0 (Inggris)](../../docs/research-plan-v0.en.md), [Versi Bahasa Mandarin](../../docs/research-plan-v0.zh.md): Model Research Object, bidang kapabilitas inti, dan matriks dekomposisi faktor.
