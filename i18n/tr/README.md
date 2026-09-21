# academic-research-kernel (tr)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Çatı-bağımsız akademik araştırma çekirdeği ve çoklu ajan müzakere paketi. Taşınabilir Agent Plugins v1 ve MCP (Model Context Protocol) giriş noktaları ile 13 akademik yetenek ve doğrulama aracı, ayrıca Hermes Agent, Claude Code, Cursor ve özel CLI alt ajanları için yerel entegrasyon sağlar. Kaynak doğrulama, literatür analizi, akademik yazım, sayısal hesaplama, nicel makale denetimi, tekrarlanabilirlik denetimleri, sistematik derleme ve meta-analiz, araştırma nesnesi kimliği ve kökeni, dinamik modeller arası çapraz hakemlik orkestrasyonu ve iki haftalık izleme otomasyonunu kapsar. Depo çalıştırılabilir örnek kontroller içerir; doğrulama kapsamı ve harici hizmet sınırlamaları [denetim raporunda](../../docs/project-lineage-audit-20260920.md) kayıtlıdır.

Yazar: Junfu Shi (SJF, xngg1021), Hermes Agent. Geçerli kapsamlı lisans teklifi: [Source Lineage License 1.0](../../LICENSE).

## Lisans

Bu bildirimi içeren anlık görüntü, [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md) dosyasında tanımlanan Kapsanan Materyal ve haklar için **Source Lineage License 1.0**'ı benimser. İlk SLL işlemesi ve ağacı ile daha sonraki sınır kaydı işlemesi [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) ve [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md) içinde ayırt edilir. Bu kayıtlı geçişten itibaren bu bildirimi koruyan anlık görüntüler aynı kapsamlı teklifi taşır.

`439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` tarihine kadar olan geçmiş anlık görüntüler MIT lisanslıdır. Alıcılar geçerli MIT izinlerini korur ve SLL'ye geçmek zorunda değildir. [Önceki proje MIT metni](../../LICENSES/MIT-pre-SLL.txt) korunmuştur; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) ve üçüncü taraf kökeni değişmeden kalır. Yeni kök teklif bu hakları silmez.

SLL; geçerli lisans, bildirim ve kaynak kökeni koşullarına tabi olarak kullanıma, incelemeye, değiştirmeye, ticari kullanıma, dağıtıma ve tescilli eklemelere geniş ölçüde izin verir. Copyleft değildir ve kaynak kodu açıklaması gerektirmez. Kopyalar sağlamadan yalnızca ağ hizmeti sunmak, Core hizmet kökeni bildirim koşulunu tek başına tetiklemez. Açık bir patent hakkı verilmez. [LICENSE](../../LICENSE) belgesinin tam İngilizce metni bu bilgilendirici özeti kontrol eder; `LicenseRef-Source-Lineage-1.0` yerel bir referanstır, SPDX ataması değildir. [Katkı alımı](../../CONTRIBUTING.md) lisans izinlerinden ayrıdır.

## Yetenekler

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

On üç yetenek genelinde 21 Markdown referans dosyası bulunmaktadır. Referanslar yalnızca gerektiğinde yüklenir.

## Akademik Standartlar ve Çoklu Profil Temel Çizgisi

Alıntı stilleri, raporlama kriterleri ve meta veri sözleşmeleri hedef dergiye, kuruma, fon sağlayıcıya, disipline ve yargı yetkisine bağlıdır. Depo; bölgesel profiller ve disiplin standartları (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE) ile birlikte **ISO 690:2021** (Bibliyografik referanslar), **ISO 5127:2017** (Bilgi ve dokümantasyon sözlüğü) ve **W3C PROV** (Köken veri modeli) standartlarını uluslararası temel çizgiler olarak belirler. Hedef yayın yerinin gereksinimleri varsayılan profillerden önce gelir. Bkz. [Akademik Standartlar Mimarisi](../../docs/standards/README.md) ve [Doğal Terminoloji Kılavuzu](../../docs/terminology/README.md).

## Entegrasyon ve Taşınabilir Kullanım

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
Bu depo, sağlayıcıdan bağımsız **Agent Plugins v1** belirtimine (`../../plugin.json`) uygundur ve temel akademik doğrulama ile istatistiksel yeniden hesaplama araçlarını stdio **MCP sunucusu** (`../../mcp.json` / `python scripts/mcp_server.py`) aracılığıyla sunar. Claude Code, Cursor, Gemini CLI ve tüm modern ajan çatılarıyla uyumludur.

```bash
# Add as stdio MCP server in your agent harness
python scripts/mcp_server.py
```

### 2. Hermes İçinde Yerel Kurulum
Bir Hermes kurulumunda şunu çalıştırın:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Tam tanımlayıcıdaki dizin adını değiştirerek diğerlerini kurun. Normal bir tap varsayılan dalı okur. `245e48008fa814b3251f50755eb656bd9fb86cb1` işlemesinde kontrol edilen paketlenmiş ilgili yetenekler: arxiv, grounded-citations, docx, pdf, manim-video.

## Veri Kaynağı Erişimi

- OpenAlex temel sorguları küçük bir günlük bütçeyle anonim olarak çalıştırılabilir (anonim $0.10/gün ve ücretsiz API anahtarıyla $1/gün, saniyede 100 istek tavanı). İsteğe bağlı anahtarı `OPENALEX_API_KEY` içinde saklayın.
- Crossref, hız sınırlamasıyla genel meta veri erişimi sağlar. Güncelleme ve Retraction Watch sinyalleri DOI kontrolleri gerektirir.
- Unpaywall, `UNPAYWALL_EMAIL` içinde gerçek bir iletişim e-postası gerektirir.
- arXiv, Europe PMC, PubMed ve DOAJ kendi politikalarına sahip tamamlayıcı kaynaklardır. Scite, Dimensions, Scopus ve Web of Science isteğe bağlı harici hizmetlerdir.

## Doğrulama

Özel bir Python ortamı kullanın. QA bağımlılıkları işaretli tüm örneklerin çalışabilmesini sağlar:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA; meta verileri, referansları, kişisel yol/gizli bilgi kalıplarını, Python sözdizimini ve işaretli kod bloklarını doğrular. Başarılı kontrollerde 0, kod/şema/kimlik hatalarında 1, aktarım/kimlik doğrulama/kota yetersizliğinde 2 döndürür.

CI; Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview, Windows x86_64, Windows ARM64, macOS ARM64 ve macOS Intel genelinde tam QA paketini çalıştırır. 717 birim testi geçer ve 40 çalıştırılabilir kod bloğu doğrulanır.

tools/longtail/ ayrık faktör eksenleri üzerinde 4096 SHA256 tohumlu aday kombinasyonu, açgözlü kapsam seçimi ve generated-scenarios.json içindeki kapsam raporunu içeren deterministik aşırı uzun kuyruk senaryo üretecini barındırır.

scripts/scfabric/ bilimsel hesaplama dokusudur: donanım sondası, veri türü kapılı arka uç kataloğu, beş iş yükü profili ve ComputeReceipt. Ölçümler [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md) içindedir.

## Araştırma ve Planlama Belgeleri

Bu belgeler bağlayıcı bir yol haritası değil, keşif amaçlı planlama referanslarıdır.

- [Sorun Atlası v0 (İngilizce)](../../docs/pain-atlas-v0.en.md), [Çince Sürüm](../../docs/pain-atlas-v0.zh.md): Akademik bilgi çalışması yaşam döngüsündeki sürtünme noktaları.
- [Araştırma Planı v0 (İngilizce)](../../docs/research-plan-v0.en.md), [Çince Sürüm](../../docs/research-plan-v0.zh.md): Research Object modeli, temel yetkinlik alanları ve faktör ayrıştırma matrisi.
