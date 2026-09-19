# academic-research-kernel (tr)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Akademik araştırmalar ve çoklu ajan istişareleri için bağımsız çekirdek. Taşınabilir Agent Plugins v1 ve MCP (Model Context Protocol) giriş noktaları ile 13 akademik beceri ve doğrulama aracı sağlar; ayrıca Hermes Agent, Claude Code, Cursor ve özel CLI alt ajanları için yerel entegrasyon sunar.

Yazar: Junfu Shi (SJF, xngg1021), Hermes Agent. Lisans: [Source Lineage License 1.0](../../LICENSE).

## Lisans

Bu anlık görüntü, [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md) dosyasında tanımlanan materyaller için **Source Lineage License 1.0** lisansını benimser. `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` öncesindeki geçmiş kopyalar MIT lisansı kapsamındadır.

## Beceriler

| Beceri | Sürüm | Açıklama |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Kimlik ve alıntı sayılarının çapraz doğrulaması; güncelleme ve geri çekme sinyallerinin denetimi; açık erişimli metin bulma ve PDF doğrulaması |
| `skills/literature-analysis` | 1.3.0 | On iki iş akışı: konu benzerliği, metin örtüşmesi, karşıt kanıtlar, yazar profilleri, deneme hakemliği ve safsata kontrolleri |
| `skills/academic-writing` | 1.1.1 | Akademik düzenleme, alıntı kılavuzları (ISO 690, APA, MLA, Chicago, IEEE, AMA ve bölgesel profiller) ve dergi kuralları |
| `skills/math-computation` | 1.2.1 | Sayısal ve istatistiksel tariflerle matematiksel alan yönlendirmesi; gelişmiş referans dosyaları |
| `skills/quantitative-paper-audit` | 1.1.0 | Bildirilen istatistiklerin yeniden hesaplanması (etki büyüklüğü, p değerleri, güven aralıkları, OR/RR) ve tutarsızlıkların tespiti |
| `skills/research-reproducibility` | 1.0.1 | Yapılandırılmış kontrol listeleri ve tekrarlanabilir denetim kayıtları içeren 14 aşamalı tekrarlanabilirlik denetim hattı |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA arama kayıtları, literatür tarama kayıtları, etki büyüklüğü dönüşümü, heterojenlik ve meta-analiz birleştirme |
| `skills/literature-watch` | 1.1.0 | Haftalık izleme: OpenAlex ve Crossref üzerinde konuları, yazarları ve DOI alıntılarını yinelemesiz takip etme |
| `skills/retraction-watch` | 1.1.0 | Haftalık izleme: OpenAlex geri çekme indeksleri ve Crossref güncellemelerine karşı DOI izleme listesini kontrol etme |
| `skills/research-object-identity` | 1.1.0 | Nedensel DAG doğrulaması ile deterministik araştırma kaynağı tanımlama ve kaynak izleme |
| `skills/claim-evidence-graph` | 1.0.0 | Bilimsel iddialar, kanıt kayıtları ve hesaplamalı kaynak arasında deterministik bağlantı kurma |
| `skills/decision-ledger` | 1.0.0 | Araştırma Karar Günlüğü: kararların, olumsuz sonuçların ve rota durumlarının deterministik, yalnızca eklemeli günlüğü |
| `skills/cross-review-five` | 2.0.0 | Kuhn-Munkres eşleştirmesi ve seyrek müzakere v2 ile heterojen modeller için dinamik çoklu hakem paneli orkestrasyonu |

## Akademik Standartlar ve Çoklu Profil Temeli

Depo, **ISO 690:2021** (Bibliyografik referanslar), **ISO 5127:2017** (Temel kavramlar ve sözlük) ve **W3C PROV** (Köken veri modeli) standartlarını uluslararası temel olarak kabul eder. Ayrıntılar için [Standartlar Mimarisi](../../docs/standards/README.md) ve [Terminoloji Kılavuzu](../../docs/terminology/README.md) belgelerine bakınız.

## Entegrasyon ve Taşınabilir Kullanım

```bash
python scripts/mcp_server.py
```

## Doğrulama ve CI

CI, tam QA paketini Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 ve macOS Intel ortamlarında, 625 başarılı birim testi ve canlı upstream canary doğrulaması ile çalıştırır.

## Araştırma ve Planlama Belgeleri

- [Zorluklar Atlası v0 (İngilizce)](../../docs/pain-atlas-v0.en.md), [Çince Sürüm](../../docs/pain-atlas-v0.zh.md): Akademik bilgi çalışması döngüsündeki sürtünme noktaları.
- [Araştırma Planı v0 (İngilizce)](../../docs/research-plan-v0.en.md), [Çince Sürüm](../../docs/research-plan-v0.zh.md): Research Object modeli, temel yetenek alanları ve faktör ayrıştırma matrisi.
