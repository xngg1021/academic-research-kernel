# academic-research-kernel (tr)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Ajan destekli bilimsel araştırma iş akışları için çalışma ortamından bağımsız, deterministik araştırma durumu yönetimi ve metodolojik doğrulama çekirdeği. Sistem; araştırma nesnesi kimliğini, ampirik kanıt / doğrulama kaydı verilerini, iddia ve kanıt ilişkileri (CEG) yapısını ve yalnızca eklenebilir araştırma kararları ve başarısız denemeler günlüğü kayıtlarını, araştırma materyallerinin içeri aktarımı ve evrensel bir Model Context Protocol (MCP) sunucusu aracılığıyla birleştirir. On dört uzmanlaşmış akademik beceri, Claude Code, Cursor, Codex, Gemini CLI ve Hermes Agent için yerel destek sunarak doğrulanmış araştırma durumunun hem üreticisi hem de tüketicisi olarak çalışır. Doğrulama kapsamı ve harici hizmet sınırlamaları [proje denetim raporunda](../../docs/project-lineage-audit-20260920.md) kayıtlıdır.

Yazar: Junfu Shi (SJF, xngg1021), Hermes Agent. Geçerli kapsamlı lisans teklifi: [Source Lineage License 1.0](../../LICENSE).

## Hızlı başlangıç

2.2.0 sürümünü [uv](https://docs.astral.sh/uv/getting-started/installation/) ile çalıştırın:

```bash
uvx academic-research-kernel@2.2.0 mcp
```

[2.2.0 sürüm notları](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.2.0), dağıtım özetlerini (hash) ve yayın durumunu içerir. Yayınlanan wheel paketi `uvx --from ./academic_research_kernel-2.2.0-py3-none-any.whl academic-research-kernel mcp` komutuyla yerel olarak da çalıştırılabilir. Python 3.10–3.14 desteklenmektedir; `uvx --python 3.12` seçeneği desteklenen bir yorumlayıcıyı açıkça seçer. İstatistiksel hesaplama modülleri dahil olmak üzere 12 deterministik aracın tamamı temel kuruluma dahildir.

## Kurulumu doğrulama

```bash
uvx academic-research-kernel@2.2.0 doctor
uvx academic-research-kernel@2.2.0 --version
```

Çevrimdışı tanılama aracı; bağımlılıkları, veri şemalarını ve 12 araç tanımının tamamını kontrol eder. İsteğe bağlı harici hizmetler yapılandırılmadan bırakılabilir. Makine tarafından okunabilir çıktı almak için `doctor --json` komutunu kullanın.

## Paket kurulumu

```bash
uv tool install academic-research-kernel==2.2.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Alternatif olarak, desteklenen bir sanal ortam içinde `pipx install academic-research-kernel==2.2.0` veya `python -m pip install academic-research-kernel==2.2.0` komutlarıyla kurulum yapabilirsiniz. `[full]` seçeneği kapsamlı bilimsel hesaplama örnekleri için gerekli kütüphaneleri ekler; `[qa]` seçeneği PDF ayrıştırıcısı dahil depo doğrulama araçlarını kurar. `[research]` seçeneği, temiz kurulumlarda tutarlı PDF yazı tipi çözümlemesi için her ikisi de Python 3.10 ile uyumlu olan `pypdf==6.19.0` ve `fonttools==4.65.0` paketlerini ekler. Yapılandırılmış HTML/XML ve boyutu sınırlandırılmış DOCX/XLSX okuma işlemleri standart kütüphaneyi kullanır. GPU arka uçları ve ücretli hizmetler isteğe bağlıdır.

## Hermes

Hermes işlem `PATH` değişkeninde `uv` aracının bulunduğundan emin olun, ardından taşınabilir eklentiyi kurup açıkça etkinleştirin:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

Mevcut `academic-skills` kimliği geriye dönük uyumluluk için korunur ve `paper-research` dahil 14 beceriyi kapsar. Eklentinin `mcp.json` yapılandırması, Python 3.12 ve deponun `uv.lock` dosyası ile `uv run --frozen --no-dev --no-editable` komutunu çağırır; çalışma ortamı `${PLUGIN_DATA}/runtime` altında tutulur. İlk kullanımda Hermes'in veya işletim sisteminin Python paketlerini ödünç almadan kendi bağımlılıklarını kurar; eksik paketleri veya yorumlayıcıyı indirmek için ilk çalıştırmada ağ erişimi gerekir. Yalnızca becerileri kuran eski tap yöntemi, aşağıdaki taşınabilir kullanım bölümünde açıklandığı şekilde desteklenmeye devam etmektedir.

## Kaynak koddan çalıştırma

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Bağımlılık sınıflandırması, yeniden üretim, sürüm kimliği, yayın kontrol noktaları ve doğrulama kapsamı için [dağıtım ve sürüm kılavuzuna](../../docs/distribution-release.md) bakın.

## Lisans

Bu bildirimi içeren anlık görüntü, [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md) dosyasında tanımlanan Kapsanan Materyal ve haklar için **Source Lineage License 1.0** lisansını benimser. İlk SLL işlemesi (commit) ve ağacı ile daha sonraki sınır kaydı işlemesi [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) ve [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md) belgelerinde birbirinden ayrılmıştır. Bu kayıtlı geçişten itibaren bu bildirimi koruyan anlık görüntüler aynı kapsamlı lisans teklifini taşır.

`439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` işlemesine kadar olan geçmiş anlık görüntüler, ilgili kopyalara uygulanan koşullar çerçevesinde MIT lisanslıydı. Alıcılar geçerli MIT izinlerini korur ve SLL'ye geçmek zorunda değildir. [Önceki proje MIT metni](../../LICENSES/MIT-pre-SLL.txt) korunmuştur; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) ve üçüncü taraf kaynak bilgileri değişmeden kalır. Yeni kök lisans teklifi bu önceki hakları ortadan kaldırmaz.

SLL; geçerli lisans, bildirim ve kaynak kökeni koşullarına tabi olmak kaydıyla kullanıma, incelemeye, değiştirmeye, ticari kullanıma, dağıtıma ve özel mülkiyetli eklemelere geniş ölçüde izin verir. Copyleft değildir ve kaynak kodu açıklaması gerektirmez. Kopya sağlamaksızın sunulan saf ağ hizmeti, tek başına Core hizmet kökeni bildirim koşulunu tetiklemez. Açık bir patent lisansı verilmez ve üçüncü taraf materyaller kendi koşullarına tabi kalır. Bu bilgilendirici özete [LICENSE](../../LICENSE) belgesinin özgün İngilizce metni esas teşkil eder; `LicenseRef-Source-Lineage-1.0` yerel bir referanstır, SPDX tarafından atanmış bir tanımlayıcı değildir ve herhangi bir OSI onayı iddia edilmez. [Katkı kabul süreci](../../CONTRIBUTING.md), alt kullanıcı lisans izinlerinden ayrıdır.

## Beceriler

| Beceri | Sürüm | İşlevi |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Yayın kimliğini ve kaynağa özgü atıf sayılarını çapraz kontrol etme; güncelleme ve geri çekme (retraction) sinyallerini inceleme; açık erişim tam metinleri bulma ve PDF kimliğini doğrulama |
| `skills/literature-analysis` | 1.3.0 | On iki analiz iş akışı: konu benzerliği, yerel metin örtüşmesi, karşıt kanıtlar, yazar profilleri, deneme hakemliği, mantık hatası kontrolü, inceleme matrisi, aday dergiler, BibTeX, iki dilli okuma, araştırma boşluğu taraması ve yeniden üretim |
| `skills/academic-writing` | 1.1.1 | Akademik metin düzenleme, atıf kılavuzu (ISO 690, APA, MLA, Chicago, IEEE, AMA ve bölgesel profiller), dergi yazım kuralları, isteğe bağlı tespit hizmetleri, başvuru belgeleri ve kurumsal gereksinimler |
| `skills/math-computation` | 1.2.1 | Düzeltilmiş sayısal ve istatistiksel örneklerle mevcut alan/görev yönlendirmesi; dört adet alana özgü ileri düzey referans dosyası |
| `skills/quantitative-paper-audit` | 1.1.0 | Makalelerde bildirilen istatistikleri (etki büyüklüğü, p değerleri, güven aralıkları, OR/RR, ulaşılan istatistiksel güç) yeniden hesaplama ve sayısal uyuşmazlıkları tespit etme |
| `skills/research-reproducibility` | 1.0.1 | Yapılandırılmış doğrulama kontrol listeleri, beş olgu doğrulama katmanı ve yeniden üretilebilir denetim kayıtları içeren on dört aşamalı tekrarlanabilirlik denetim hattı |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA arama kayıtları, literatür tarama ve eleme kaydı, etki büyüklüğü dönüştürme, heterojenlik, sabit/rastgele etkili birleştirme, duyarlılık ve yayın yanlılığı tanılama |
| `skills/literature-watch` | 1.1.0 | Haftalık izleme: OpenAlex ve Crossref üzerinde konuları, yazarları ve DOI'ye atıf yapan çalışmaları izleme; mükerrer kayıtları ayıklama ve yalnızca yeni yayınları raporlama |
| `skills/retraction-watch` | 1.1.0 | Haftalık izleme: Bir DOI izleme listesini OpenAlex `is_retracted` durumu ve Crossref güncelleme kayıtlarına (`update-to` sinyalleri) karşı yeniden kontrol etme; yalnızca durum değişikliklerini bildirme |
| `skills/research-object-identity` | 1.1.0 | Deterministik araştırma kaynağı tanımlama ve kaynak / izlenebilirlik takibi: tanımlayıcı normalleştirme, 5 durumlu doğrulama, içerik adresli türetme çizgeleri, nedensel DAG doğrulaması ve 100 ms altında soy izleme |
| `skills/claim-evidence-graph` | 1.0.0 | Bilimsel savları, kanıt kayıtlarını ve hesaplamalı kökeni birbirine bağlayan deterministik iddia ve kanıt ilişkileri |
| `skills/decision-ledger` | 1.0.0 | Araştırma kararları ve başarısız denemeler günlüğü: bilimsel seçimlerin, olumsuz sonuçların, araştırma rotası durumu / bu yönün durdurulma nedeni kayıtlarının ve sonuç revizyonlarının deterministik, yalnızca eklemeli günlüğü |
| `skills/paper-research` | 1.0.0 | Doğrulanmış alan adayları, istatistiksel kontroller, kalıcı araştırma durumu, kaynağa bağlı Çince raporlar ve iki makale karşılaştırması ile DOI/URL/yerel makale ve ek materyal okuma |
| `skills/cross-review-five` | 2.0.0 | Keyfi modelleri ve alt ajanları (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini vb.) destekleyen dinamik çoklu hakem paneli orkestrasyonu: Kuhn-Munkres Macar ataması, sav düzeyinde kümeleme, hedefli anonim itiraz ve P0–P3 ciddiyet derecelendirmesi içeren v2 Sparse Deliberation hattı |

On dört beceri genelinde 22 adet Markdown referans dosyası bulunmaktadır. Referans dosyaları yalnızca ihtiyaç duyulduğunda yüklenir.

## Akademik Standartlar ve Çoklu Profil Temel Çizgisi

Atıf stilleri, raporlama ölçütleri ve meta veri sözleşmeleri hedef dergiye, kuruma, fon sağlayıcıya, disipline ve yargı yetkisine göre değişir. Depo; bölgesel profiller (örneğin Çin Ana Karası'nda GB/T 7714-2025, İspanya'da UNE-ISO 690:2024, Almanya'da DIN ISO 690:2021) ve disipliner standartlar (APA 7. baskı, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE) ile birlikte **ISO 690:2021** (Bibliyografik referanslar), **ISO 5127:2017** (Bilgi ve dokümantasyon sözlüğü) ve **W3C PROV** (Köken veri modeli) standartlarını uluslararası temel çizgiler olarak belirler. Hedef yayın yerinin gereksinimleri varsayılan profillerden önce gelir. Ayrıntılar için [Akademik Standartlar Mimarisi](../../docs/standards/README.md) ve [Doğal Terminoloji Kılavuzu](../../docs/terminology/README.md) belgelerine bakın.

Son bütünlük onarımı; DOI/tanımlayıcı tutarlılığını, nicel karar bayraklarının karşılıklı dışlayıcılığını ve çekirdek ile alındı kayıtları arasındaki ortak incelenmesi gereken hususlar sözleşmesini doğrular. Önbellek bütünlüğü, alındının mutasyon listelerinden bağımsız olarak, korunan kaynak zarflarından ve normalleştirilmiş bağlardan yeniden oluşturulur; hem bir kaydın hem de önbellek bildiriminin silinmesi kabul edilen bir yeniden oynatma üretemez. Bkz. [dört engelleyici sorunun kapanış raporu](../../docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Entegrasyon ve Taşınabilir Kullanım

### 1. Universal Agent Plugins v1 ve Model Context Protocol (MCP)
Bu depo, sağlayıcıdan bağımsız **Agent Plugins v1** belirtimine (`../../plugin.json`) uygundur ve temel akademik doğrulama ile istatistiksel yeniden hesaplama araçlarını bir stdio **MCP sunucusu** (`../../mcp.json` / `../../scripts/mcp_server.py`) aracılığıyla sunar. Claude Code, Cursor, Gemini CLI ve tüm modern ajan çalışma ortamlarıyla uyumludur. Depo kimliği `academic-research-kernel` olsa da, eklenti bildirim adı `academic-skills` ve MCP yapılandırma takma adları geriye dönük uyumluluk için sabit tutulmuştur.

```bash
# Add as stdio MCP server in your agent harness
uvx academic-research-kernel mcp
```

### 2. Hermes İçinde Yerel Kurulum
Kurulu bir Hermes ortamından:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Tam tanımlayıcıdaki dizin adını değiştirerek diğer becerileri kurabilirsiniz. Normal bir tap komutu varsayılan dalı okur ve yukarıdaki beceri setini kurar. Bir çalışma dalını birleştirmeden önce incelemek için ilgili dalı yerel olarak indirin ve kurulu Hermes sürümünün yerel klasörden kurulum talimatlarını izleyin; tap komutunun bir inceleme dalını otomatik seçeceğini varsaymayın.

Üst kaynak `245e48008fa814b3251f50755eb656bd9fb86cb1` anlık görüntüsünde kontrol edilen paketlenmiş ilgili beceriler: arxiv, grounded-citations, docx, pdf ve manim-video. huggingface-hub ve llama-cpp isteğe bağlı katalogda yer alır ve ayrıca kurulmaları gerekebilir. ocr-and-documents ve pc-hardware-benchmark bu anlık görüntüde bulunmamaktadır ve bağımlılık değildir. Oturum araçları ile belge/tarayıcı arka uçları yerel yapılandırmaya bağlıdır.

## Veri Kaynağı Erişimi

- OpenAlex temel sorguları daha küçük bir günlük bütçeyle anonim olarak çalıştırılabilir. 2026-09-06 tarihinde kontrol edilen belgelere göre anonim kullanım için günlük 0,10 ABD doları, ücretsiz API anahtarıyla günlük 1 ABD doları bütçe ve saniyede 100 istek tavanı uygulanmaktadır. Maliyetler sorgu türüne göre değişir ve sınırsız erişim anlamına gelmez. İsteğe bağlı anahtarı `OPENALEX_API_KEY` değişkeninde saklayın; `per_page` (en fazla 100) ve imleç tabanlı sayfalama kullanın.
- Crossref, hız sınırlandırmalı genel meta veri erişimi sunar. Güncelleme ilişkileri ve Retraction Watch sinyalleri DOI ve yön kontrolü gerektirir; kayıt bulunmaması bir makalenin etkilenmediğini kanıtlamaz.
- Unpaywall, `UNPAYWALL_EMAIL` değişkeninde gerçek bir iletişim e-posta adresi gerektirir. Bir konum dönmemesi, açık erişimli kopya bulunmadığını kanıtlamaz.
- arXiv, Europe PMC, PubMed E-utilities ve DOAJ kendi kullanım politikalarına sahip tamamlayıcı kaynaklardır ve varsayılan testlerin tamamında çağrılmazlar. Semantic Scholar paylaşımlı anonim sınırlar ve ayrı atanmış anahtar kotaları uygular; API erişimi atıf bağlamının her zaman sunulacağını garanti etmez.
- Scite, Dimensions, Scopus, Web of Science ve yapay zeka tespit ürünleri isteğe bağlı harici hizmetlerdir. Kullanmadan önce mevcut hesap/API yetkilerini ve kotaları kontrol edin; evrensel ücretsiz katman veya sabit fiyat taahhüt edilmez.

Ayrıntılar için [OpenAlex kimlik doğrulaması](https://help.openalex.org/api/authentication/), [bütçeler ve sorgu maliyetleri](https://help.openalex.org/api/llm-quick-reference/) ve [Crossref güncelleme filtreleri](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/) belgelerine bakın.

## Deterministik içeri aktarım ve açık çekirdek

Araştırma materyallerinin içeri aktarımı katmanı; `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 adaptör (14 beceri artı `opaque fallback`) ve 12 durumsuz (stateless) stdio MCP aracı sağlar. Kabul edilen içeri aktarım alındıları, korunan her anlamsal değişikliği türüne, kimliğine ve kurallı SHA-256 özetine göre bağlar: araştırma nesneleri, iddia ve kanıt ilişkileri (CEG) kayıtları, karar günlüğü kayıtları, incelenmesi gereken hususlar, fiziksel alındılar ve materyal kayıtları. Önbellekten yeniden oynatma, bu taahhütleri aktarım anlık görüntüsü özetlerinden bağımsız olarak denetler. Boş günlükler geçerlidir; başarısız olan atomik toplu işlemler kısmi durum bırakmaz.

Köken içerik yetkisi açıktır ve bant dışından (out-of-band) iletilir. Güvenilir Python çağrıcıları, serileştirilmiş alındıları veya anlık görüntüleri yeniden oynatırken `LineageVerificationContext` nesnesini iletir; MCP çağrıcıları ise yalnızca sınırlandırılmış içerik baytları sağlayabilir, hiçbir zaman ana bilgisayar dosya sistemi kökünü iletemez. Varsayılan içerik bütçesi 10 MiB'dir; güvenilir bir ana sistem, üretici ve doğrulayıcı arasında aynı politika altında daha büyük materyallere açıkça izin verebilir. İçerik yetkisi olmadan `fully_verified` iddiası bağımsız olarak yeniden üretilemez ve yapılandırılmış bir geçersiz doğrulama sonucu döndürür. Yapılandırılmamış düz metinler opak kalır, karşıt görüşler görünür biçimde korunur ve araştırmacılar işlemeler, araştırma rotalarını sonlandırma veya yeniden açma, yönlendirme ve bilimsel doğruluk kararları üzerindeki kontrolü elinde tutar.

Sözleşmeler ve uyumluluk kuralları için [çekirdek mimarisi](../../docs/kernel-architecture.md) belgesine bakın. Dağıtım ve yayın kontrol noktaları [yayın kılavuzunda](../../docs/distribution-release.md) kayıtlıdır. İngilizce ve Basitleştirilmiş Çince README dosyaları güncel tutulmakta olup, diğer çevirilerin durumu [eşitleme bildiriminde](../../docs/i18n/manifest.json) açıkça izlenmektedir. Son aday kimliği, tam HEAD CI sonuçları ve birikimli inceleme kanıtları [kapanış günlüğünde](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342) yer almaktadır.

## Doğrulama

Adanmış bir Python ortamı kullanın. Çalışma zamanı kütüphaneleri göreve özgüdür ve Hermes içinde kurulu oldukları garanti edilmez. İşaretli tüm örneklerin çalışabilmesi için QA bağımlılıkları daha kapsamlıdır:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

QA betiği; meta verileri, yerel referansları, kişisel dosya yolu ve bilinen gizli anahtar kalıplarını, Python sözdizimini ve işaretlenmiş çalıştırılabilir kod bloklarını doğrular. Her `smoke` örneği yeni bir alt işlemde değiştirilmeden çalıştırılır. Grafik örnekleri `PLOT_DIR` değişkenini (varsayılan `~/plots`, açıkça genişletilir) kabul eder ve testler sırasında geçici bir dizin kullanır. Sınıflandırılmamış Python kod blokları reddedilir; `fragment:` blokları sözdizimi açısından denetlenir ancak adlandırılmış girdiler gerektirir ve tek başına çalıştırılmaz. `external-test:` blokları yalnızca manuel harici doğrulama komutuyla çalıştırılır; yapılandırılmış kontroller geçtiğinde `0`, kod/şema/kimlik hatasında `1`, aktarım/kimlik doğrulama/kota yetersizliğinde `2` döndürür; yapılandırılmamış isteğe bağlı hizmetler `SKIP` olarak kalır.

Sabitlenmiş Hermes beceri yazım testleri, beceri başına kuralları değiştirilmeden yeniden kullanılır. Üst kaynağın tüm dağıtımı kapsayan genel kontrolleri bu depo için geçerli değildir; test altyapımız on dört beceriyi denetler ve referansları sabitlenmiş yerleşik/isteğe bağlı kataloğa göre çözümler. Bu işlem tam bir Hermes kurulum testi değildir. CI ağı yalnızca bağımlılıkları kurmak için kullanır; olağan değişiklik testleri akademik API'leri çağırmaz.

CI; Linux x86_64 (Python 3.10–3.14), Linux ARM64 (`ubuntu-24.04-arm`), Ubuntu 26.04 preview canary (`ubuntu-26.04` ve `ubuntu-26.04-arm`), Windows x86_64, Windows ARM64 (`windows-11-arm`), macOS ARM64 (`macos-latest`) ve macOS Intel (`macos-15-intel`) üzerinde canlı üst kaynak canary doğrulamasıyla birlikte tam QA paketini çalıştırır. Geçmiş temel aday 1165 yerel testi geçmiştir. Güncel onarım sonuçları ve kapsam sınırları [doğruluk onarımı raporunda](../../docs/maintenance/correctness-repair-20261008.md) kayıtlıdır; uzak test kanıtları test edilen `HEAD` işlemesini ayrıca belirtir. `main` dalına yapılan göndermelerde ayrı bir tap entegrasyon iş akışı çalışır: `tests/upstream/provenance.json` içinde kayıtlı sabitlenmiş Hermes kopyasını kurar ve bu depoya karşı `tap add`, `search`, `install` ve `list` komutlarını sınar. Tam sürümler, kontroller ve sınırlamalar [denetim raporunda](../../docs/project-lineage-audit-20260920.md) yer almaktadır.

[tools/longtail/](../../tools/longtail/README.md) dizini deterministik uzun kuyruk faktör üretecini barındırır: SHA-256 tohumlu 4096 aday, seçilen 30 senaryo ve makine tarafından hesaplanan bir doğrulama kapsamı raporu. v3 modeli; yetenek ailelerini (E01), depodaki 14 gerçek beceriyi (E02) ve görev hedeflerini (E03) ayrı ayrı sayar. Her senaryonun bir birincil becerisi, desteklenen bir görev hedefi ve uyumlu yetenekleri vardır; her beceri, beyan edilen temel hedefi dahil olmak üzere iki farklı hedef altında en az iki kez yer almalıdır. Beceri dizini kayması doğrulamayı başarısız kılar. Anlamsal genişletme (görev zincirleri, doğrulama ölçütleri ve yürütülen olay enjeksiyonu) ayrı bir aşamadır; faktör kapsamı iş akışı yürütme kapsamını kanıtlamaz.

`scripts/scfabric/` dizini bilimsel hesaplama ve istatistik araç seti katmanıdır: donanım sondası, veri türü (`dtype`) geçitlerine sahip arka uç kataloğu, beş iş yükü profili, eşlik kabulüne sahip eşleştirilmiş kıyaslama ve `ComputeReceipt`. Bu makinedeki ilk tur ölçümleri [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md) belgesindedir; genel kural varsayılan olarak CPU kullanmak, hızlandırıcıları ise yalnızca doğrulama alındısı ile etkinleştirmektir.

## Yerel bir Ajan ile makale araştırma

`academic-research-kernel[research]==2.2.0` paketini kurun ve paketlenmiş iş akışını dışa aktarın:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Work veya uyumlu bir yerel Ajanın dışa aktarılan bu `SKILL.md` dosyasını okumasına izin verin ve ardından şunu isteyin:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Yalnızca DOI'yi, açık bağlantıyı veya yerel dosya paketini sağlamanız yeterlidir. İki makale için Ajandan verileri, yöntemleri, değerlendirme koşullarını ve sonuçları karşılaştırmasını, nelerin doğrudan karşılaştırılabilir olduğunu açıklamasını isteyin. Ajan aynı görev içinde özgün metin okuma, aday alan doğrulaması, istatistiksel hesaplama, çekirdeğe aktarım, rapor oluşturma ve bağımsız kaynak incelemesi adımlarını sürdürür. Mevcut MCP yüzeyi 12 aracını korur; yeni orkestrasyon CLI ve taşınabilir beceri üzerinden çalışır.

Programın gerçek çalışma aşamaları şunlardır:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` komutu materyali temin eder ve bir bildirim dosyası, kaynak özetleri (hash) ile konumu belirlenmiş metin bölümlerine ayrıştırır. `finish` komutu, Ajan tarafından üretilen çıkarımı doğrular ve mevcut istatistiksel araçları kullanarak uygun t/p testlerini, iki gruplu etki büyüklüğü ve sayı/yüzde iddialarını yeniden hesaplar, ardından çekirdek durumunu ve Çince Markdown/HTML raporlarını kaydeder. `compare` komutu, Ajanın karşılaştırılabilir koşullara ilişkin açık değerlendirmesini doğrular. Bu komutlar yerleşik bir dil modeli barındırmaz: anlamsal okuma, [paper-research](../../skills/paper-research/SKILL.md) kılavuzunu izleyen mevcut Ajan tarafından gerçekleştirilir. Kaydedilen özgün dosyalar ve çıkarım anlık görüntüleri deterministik çevrimdışı yeniden oynatmayı destekler; ağ üzerinden edinim ve yeni bir anlamsal okuma ayrı tanımlanan işlemler olarak kalır.

## 2.0.1 doğruluk onarımları ve dağıtım doğrulaması

2.0.1 ürün sürümü, istatistiksel hesaplama ve protokol doğruluk onarımlarını içerir. Açık `academic_recompute_statistics` aracı t-testi p değerlerini ve iki gruplu Cohen `d` / Hedges `g` katsayılarını sunar; güven aralıkları (CI) ve `OR/RR` hesaplamaları alt düzey Python işlevleri olarak kalır. Raporlanan hassasiyet önemli olduğunda `p_value_literal` (örneğin `"1.0e-5"`) veya `p_value_decimals` parametresini sağlayın. Metin biçimindeki değerler sondaki sıfırları korurken, sayısal girdiler yalnızca sayısal gösterimlerini korur; çelişen hassasiyet kaynakları açıkça hata verir. Yarıdan yukarı yuvarlama (`round-half-up`) karşılaştırmaları alt yuvarlama sınırını dahil eder ve üst sınırı hariç tutar. Olağan bir sayısal uyuşmazlık başarılı bir bilimsel bulgudur; geçersiz veya kısmen başarısız hesaplamalar ise `isError` bayrağını ayarlar.

Geri çekme (retraction) kontrolleri, mevcut `True`/`False`/`unknown` gözlemini bilinen son değerden ayrı olarak kaydeder. Sorgu öncesi kısa bir rezervasyon, aynı DOI için yapılan gözlemleri sıralar ve diğer DOI güncellemelerini korur. Mevcut gözlemler ve geçmiş doğrulamalar ayrı sürümlere sahiptir: geç ulaşan bir doğrulama korunan geçmişi iyileştirebilirken, daha yeni bir `unknown` durumu mevcut kontrol için açıkça doğrulanmamış olarak kalır. Regresyon zincirlerindeki HTTP test verileri açıkça etiketlenmiştir.

MCP sunucusu `ping` isteklerine yanıt verir, geçerli bildirimler (`notifications/cancelled` dahil) için sessiz kalır ve geçersiz girdiden sonra stdio oturumunu açık tutar. Eşzamanlı uygulama, önceden kesmeli (preemptive) iptal bildiriminde bulunmaz. İleti işleme, [MCP ileti sözleşmesini](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) ve [ping belirtimini](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping) izler.

Bu çalışma kopyasının dağıtımlarını yalıtılmış bir ortamda derleyin ve doğrulayın:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` seçeneği aday `sdist` paketini çalışma dizini dışında değiştirmeden açar, `ARK_REPO` ve `ARK_SDIST` değişkenlerini bu adaya ayarlar ve testlerini, statik QA kontrollerini, çalıştırılabilir kod bloklarını ve i18n denetimini yürütür. Wheel ve sdist kurulumlarının her biri temiz bir ortam kullanır; `uvx` bağımsız bir önbellekle yerel wheel paketini kullanır. Rapor, materyal özetlerini ve kurulu içe aktarma yollarını kaydeder. Zamanlanmış hafif sabitlenmiş/güncel Hermes kontrolleri test edilen SHA değerini bağımsız olarak bildirir. Harici sözleşme JSON dosyaları ve iş özetleri `healthy`, `degraded` ve `failed` durumlarını kullanır; atlanan yoklamalar açıkça belirtilir.

## Araştırma ve planlama belgeleri

Bu iki belge bağlayıcı bir yol haritası değil, keşif amaçlı planlama referanslarıdır. Belgelerdeki yön numaraları `docs/direction-primitive-mapping.json` içindeki kayıtlı gruplamadan yeniden hesaplanır.

- [Pain Atlas v0 (İngilizce)](../../docs/pain-atlas-v0.en.md), [中文版](../../docs/pain-atlas-v0.zh.md): nicel iddialara eklenmiş doğrulama durumlarıyla birlikte akademik bilgi çalışması yaşam döngüsündeki sürtünme noktaları.
- [Research Plan v0 (İngilizce)](../../docs/research-plan-v0.en.md), [中文版](../../docs/research-plan-v0.zh.md): Research Object modeli, temel yetenek alanları, aday yönler ve birinci aşama faktör ayrıştırma matrisi.
