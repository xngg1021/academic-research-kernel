# academic-research-kernel (sw)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Mfumo thabiti wa kusimamia hali ya utafiti wa kitaaluma kwa mitiririko ya kazi inayotumia maajenti, unaofanya kazi bila kufungamana na jukwaa mahususi. Mfumo huu unaunganisha utambulisho wa vitu vya utafiti, kumbukumbu ya ushahidi / uthibitisho wa kimajaribio, uhusiano kati ya madai na ushahidi (CEG), na kumbukumbu ya maamuzi ya utafiti na majaribio yasiyofanikiwa inayoongezwa tu kupitia mfumo wa upokeaji wa mabaki ya utafiti na seva ya jumla ya Model Context Protocol (MCP). Stadi 14 maalum za kitaaluma huzalisha na kutumia hali ya utafiti iliyothibitishwa, zikiwa na uoanifu wa moja kwa moja na Claude Code, Cursor, Codex, Gemini CLI na Hermes Agent. Upeo wa uthibitishaji na mipaka ya huduma za nje imehifadhiwa katika [ripoti ya ukaguzi](../../docs/project-lineage-audit-20260920.md).

Mwandishi: Junfu Shi (SJF, xngg1021), Hermes Agent. Ofa ya leseni ya sasa: [Source Lineage License 1.0](../../LICENSE).

## Kuanza haraka

Endesha toleo la 2.2.0 ukitumia [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx academic-research-kernel@2.2.0 mcp
```

[Toleo la 2.2.0](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.2.0) linarekodi alama zaรหัส (hashes) za usambazaji na hali ya uchapishaji. Kifurushi cha wheel pia kinaweza kuendeshwa kwenye kompyuta yako kwa amri `uvx --from ./academic_research_kernel-2.2.0-py3-none-any.whl academic-research-kernel mcp`. Python 3.10–3.14 inatumika; chaguo la `uvx --python 3.12` huchagua moja kwa moja mkalimani anayekubalika. Zana zote 12 thabiti pamoja na zana za hesabu za kisayansi na takwimu zimejumuishwa kwenye usakinishaji wa msingi.

## Thibitisha usakinishaji

```bash
uvx academic-research-kernel@2.2.0 doctor
uvx academic-research-kernel@2.2.0 --version
```

Ukaguzi wa nje ya mtandao (offline) unahakiki programu tegemezi, miundo ya data (schemas) na ufafanuzi wa zana zote 12. Huduma za hiari za nje zinaweza kuachwa bila kusanidiwa. Tumia `doctor --json` kupata matokeo yanayosomeka kwa mashine.

## Usakinishaji wa kifurushi

```bash
uv tool install academic-research-kernel==2.2.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Vinginevyo, sakinisha kwa kutumia `pipx install academic-research-kernel==2.2.0` au `python -m pip install academic-research-kernel==2.2.0` ndani ya mazingira pepe yanayokubalika. Chaguo la `[full]` huongeza maktaba kwa ajili ya mifano mipana ya kisayansi; `[qa]` huongeza zana za kuhakiki hifadhi ikiwemo kisoma PDF. Chaguo la `[research]` huongeza `pypdf==6.19.0` na `fonttools==4.65.0` ili kuhakikisha usimbuzi thabiti wa fonti za PDF kwenye usakinishaji mpya; zote mbili zinafanya kazi na Python 3.10. Usomaji wa HTML/XML yenye muundo na faili za DOCX/XLSX zenye mipaka ya ukubwa hutumia maktaba ya kawaida ya Python. Viendeshi vya GPU na huduma za kulipia vinabaki kuwa vya hiari.

## Hermes

Sakinisha uv ili ipatikane kwenye PATH ya mchakato wa Hermes, kisha sakinisha na uwashe programu-jalizi inayobebeka:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

Utambulisho uliopo wa `academic-skills` umehifadhiwa ukiwa na stadi 14 ikiwemo `paper-research`. Faili ya `mcp.json` ya programu-jalizi huita `uv run --frozen --no-dev --no-editable` kwa kutumia Python 3.12 na faili ya `uv.lock` ya hifadhi; mazingira yake ya kuendeshea yanaishi ndani ya `${PLUGIN_DATA}/runtime`. Inapakua na kuandaa programu tegemezi mara ya kwanza inapotumiwa bila kuazima vifurushi vya Python vya Hermes au vya mfumo wa uendeshaji. Matumizi ya kwanza yanahitaji mtandao ili kupata vifurushi au mkalimani anayekosekana. Njia ya zamani ya kusakinisha stadi pekee kupitia tap bado inakubaliwa chini ya sehemu ya muunganisho na matumizi yanayohamishika.

## Kutoka kwenye msimbo chanzi

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Angalia [usambazaji na utoaji](../../docs/distribution-release.md) kwa uainishaji wa programu tegemezi, hatua za kurudia matokeo, utambulisho wa toleo, vituo vya ukaguzi wa uchapishaji na upeo wa uthibitishaji.

## Leseni

Picha ya hifadhi iliyo na taarifa hii inatumia **Source Lineage License 1.0** kwa Nyenzo Zilizofunikwa na haki zilizoainishwa katika [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Ahadi (commit) na mti wa kwanza wa SLL, pamoja na ahadi ya baadaye iliyorekodi mpaka wa mabadiliko, zimetofautishwa katika [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) na [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Matoleo yanayoendelea kutoka kwenye mpito huo uliorekodiwa ambayo yanabaki na taarifa hii yanabeba ofa sawa ya leseni.

Matoleo ya kihistoria hadi kufikia `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` yalikuwa chini ya leseni ya MIT, kulingana na masharti yaliyotumika kwa nakala hizo. Wapokeaji wanabaki na ruhusa halali za MIT na hawalazimiki kuhamia SLL. [Maandishi ya awali ya MIT ya mradi](../../LICENSES/MIT-pre-SLL.txt) yamehifadhiwa; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) na asili yake ya wahusika wengine imebaki bila kubadilishwa. Ofa mpya ya msingi haifuti haki hizo za awali.

SLL inaruhusu kwa upana matumizi, uchunguzi, marekebisho, matumizi ya kibiashara, usambazaji na nyongeza za umiliki binafsi, kwa kuzingatia masharti yanayotumika ya leseni, ilani na ufuatiliaji wa asili ya chanzo. Si leseni ya copyleft na haihitaji ufichuzi wa msimbo chanzi.utoaji wa huduma ya mtandao pekee bila kusambaza nakala hausababishi peke yake sharti la ilani ya asili ya huduma ya Core. Hakuna utoaji wa moja kwa moja wa haki za hataza (patent). Nyenzo za wahusika wengine zinabaki chini ya masharti yake husika. Maandishi halisi ya Kiingereza ya [LICENSE](../../LICENSE) ndiyo yanayoongoza muhtasari huu wa taarifa; `LicenseRef-Source-Lineage-1.0` ni rejeleo la ndani, si mgawo wa SPDX, na hakuna dai la uidhinishaji wa OSI. [Utaratibu wa kupokea michango](../../CONTRIBUTING.md) umetenganishwa na ruhusa za leseni kwa watumiaji.

## Ujuzi

| Ujuzi | Toleo | Kinachofanyika |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Uhakiki mtambuka wa utambulisho na idadi ya nukuu kulingana na chanzo; ukaguzi wa ishara za masasisho au kuondolewa kwa chapisho; utafutaji wa maandishi ya ufikiaji wazi (OA) na uhakiki wa faili za PDF |
| `skills/literature-analysis` | 1.3.0 | Mitiririko kumi na miwili ya kazi: ulinganifu wa mada, mwingiliano wa maandishi, ushahidi kinzani, wasifu wa waandishi, tathmini ya mfano, ukaguzi wa upotoshaji wa kimantiki, jedwali la mapitio, mapendekezo ya majarida, BibTeX, usomaji wa lugha mbili, uchunguzi wa mapengo ya utafiti na urudiaji |
| `skills/academic-writing` | 1.1.1 | Uhariri wa kitaaluma, mwongozo wa nukuu (ISO 690, APA, MLA, Chicago, IEEE, AMA na wasifu wa kikanda), maelekezo ya majarida, huduma za hiari za ugunduzi, nyaraka za uwasilishaji na mahitaji ya taasisi |
| `skills/math-computation` | 1.2.1 | Uelekezaji wa kazi na nyanja za kihesabu ukiwa na mifano iliyosahihishwa ya namba na takwimu; faili nne za marejeleo ya kina |
| `skills/quantitative-paper-audit` | 1.1.0 | Ukokotoaji upya wa takwimu zilizoripotiwa (ukubwa wa athari, thamani za p, vipindi vya uaminifu, OR/RR, nguvu ya takwimu iliyofikiwa) na utambuzi wa tofauti za namba |
| `skills/research-reproducibility` | 1.0.1 | Mfumo wa hatua kumi na nne wa ukaguzi wa uwezo wa kurudia matokeo wenye kikagua sheria za kurudiwa kwa matokeo, ngazi tano za ukweli na rekodi za ukaguzi zinazoweza kurudiwa |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Kumbukumbu za utafutaji za PRISMA, kumbukumbu ya uchunguzi wa machapisho, ubadilishaji wa ukubwa wa athari, uchambuzi wa utofauti, ujumuishaji wa athari maalum/nasibu, unyeti na uchunguzi wa upendeleo wa uchapishaji |
| `skills/literature-watch` | 1.1.0 | Mpango wa kila wiki: fuatilia mada, waandishi na kazi mpya zinazonukuu DOI kwenye OpenAlex na Crossref; ondoa marudio na uripoti vipengele vipya pekee |
| `skills/retraction-watch` | 1.1.0 | Mpango wa kila wiki: kagua upya orodha ya DOI dhidi ya alama ya `is_retracted` ya OpenAlex na rekodi za masasisho (`update-to`) za Crossref; ripoti mabadiliko ya hali pekee |
| `skills/research-object-identity` | 1.1.0 | Utambulisho thabiti wa rasilimali za utafiti na asili / ufuatiliaji wa mabaki ya utafiti: usanifishaji wa vitambulisho, uthibitishaji wa hali 5, grafu za mnyambuliko zinazolenga maudhui, uhakiki wa DAG ya kisababishi na ufuatiliaji wa chini ya 100ms |
| `skills/claim-evidence-graph` | 1.0.0 | Uunganishaji thabiti wa uhusiano kati ya madai na ushahidi wa kisayansi unaounganisha hoja, kumbukumbu ya ushahidi / uthibitisho na asili ya kimahesabu |
| `skills/decision-ledger` | 1.0.0 | Kumbukumbu ya maamuzi ya utafiti na majaribio yasiyofanikiwa: rekodi thabiti inayoongezwa tu ya chaguzi za utafiti, matokeo hasi, hali ya mwelekeo / kwa nini njia hii ilisitishwa na marekebisho ya matokeo |
| `skills/paper-research` | 1.0.0 | Usomaji wa makala na nyongeza kupitia DOI/URL/faili za ndani ukiwa na uhakiki wa sehemu zilizopendekezwa, ukaguzi wa takwimu, uhifadhi wa hali ya utafiti, ripoti za Kichina zenye vyanzo na ulinganishaji wa makala mbili |
| `skills/cross-review-five` | 2.0.0 | Uratibu wa jopo la wakaguzi wengi linalotumia miundo na maajenti mbalimbali (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini, n.k.): mtiririko wa Sparse Deliberation v2 wenye ugawaji wa Kuhn-Munkres Hungarian, uwekaji wa hoja katika makundi, maswali lengwa yasiyomtaja mwandishi na upangaji wa ukali wa P0–P3 |

Kuna faili 22 za marejeleo ya Markdown katika stadi kumi na nne. Marejeleo hupakiwa pale tu yanapohitajika.

## Viwango vya kitaaluma na msingi wa wasifu mbalimbali

Mitindo ya unukuu, vigezo vya kuripoti na mikataba ya metadata hutegemea jarida lengwa, taasisi, mfadhili, taaluma na mamlaka ya kisheria. Hifadhi hii inaweka **ISO 690:2021** (Marejeleo ya kibibliografia), **ISO 5127:2017** (Msamiati wa habari na nyaraka) na **W3C PROV** (Muundo wa data ya asili) kama misingi ya kimataifa, pamoja na wasifu wa kikanda (kama vile GB/T 7714-2025 nchini China Bara, UNE-ISO 690:2024 nchini Uhispania, DIN ISO 690:2021 nchini Ujerumani) na viwango vya kitaaluma (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Mahitaji ya chapisho lengwa yanapewa kipaumbele dhidi ya wasifu chaguo-msingi. Tazama [Muundo wa Viwango vya Kitaaluma](../../docs/standards/README.md) na [Mwongozo wa Istilahi za Kawaida](../../docs/terminology/README.md).

Marekebisho ya mwisho ya uthibitishaji yanahakiki uwiano wa DOI na vitambulisho, alama za uamuzi wa kiasi zinazopingana, na mkataba wa pamoja wa vipengele vinavyohitaji ukaguzi kati ya kiini na stakabadhi. Ukamilifu wa hifadhi ya muda (cache) unajengwa upya kutoka kwenye bahasha za vyanzo zilizohifadhiwa na vifungo vilivyosanifishwa, bila kutegemea orodha za mabadiliko za stakabadhi; kuondoa kwa pamoja rekodi na tamko lake la hifadhi ya muda hakuwezi kuzalisha marudio yanayokubaliwa. Angalia [ufungaji wa vizuizi vinne](../../docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Muunganisho na matumizi yanayohamishika

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
Hifadhi hii inafuata vipimo visivyofungamana na muuzaji vya **Agent Plugins v1** (`../../plugin.json`) na hutoa zana za msingi za uhakiki wa kitaaluma na ukokotoaji upya wa takwimu kupitia **seva ya MCP** ya stdio (`../../mcp.json` / `../../scripts/mcp_server.py`). Inaoana na Claude Code, Cursor, Gemini CLI na mfumo wowote wa kisasa wa maajenti. (Kumbuka: Ingawa utambulisho wa hifadhi ni `academic-research-kernel`, jina la dhihirisho la programu-jalizi `academic-skills` na lakabu za usanidi wa MCP zinabaki thabiti kwa uoanifu wa nyuma.)

```bash
# Add as stdio MCP server in your agent harness
uvx academic-research-kernel mcp
```

### 2. Usakinishaji wa asili katika Hermes
Kutoka kwenye usakinishaji wa Hermes:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Sakinisha stadi nyingine kwa kubadilisha jina la saraka kwenye kitambulisho kamili. Tap ya kawaida husoma tawi chaguo-msingi, kwa hivyo seti ya stadi iliyo hapo juu ndiyo inayosakinishwa na tap mpya. Ili kukagua tawi la kazi kabla ya kuunganishwa, pakua tawi hilo kwenye kompyuta yako na ufuate maelekezo ya usakinishaji wa folda ya ndani ya toleo la Hermes ulilosakinisha. Usidhani kuwa amri ya tap inachagua tawi la majaribio.

Stadi zinazohusiana zilizofungashwa pamoja zilikaguliwa kwenye toleo la juu `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video. Vifurushi vya huggingface-hub na llama-cpp viko kwenye orodha ya hiari na vinaweza kuhitaji kusakinishwa tofauti. ocr-and-documents na pc-hardware-benchmark hazikupatikana kwenye picha hiyo na si programu tegemezi. Zana za vipindi na viendeshi vya nyaraka au kivinjari hutegemea usanidi wa kompyuta husika.

## Ufikiaji wa vyanzo vya data

- Maswali ya msingi ya OpenAlex yanaweza kuendeshwa bila kujitambulisha kwa bajeti ndogo ya kila siku. Nyaraka za tarehe 2026-09-06 zinaonyesha $0.10/siku bila kujitambulisha na $1/siku kwa ufunguo wa bure wa API, pamoja na ukomo wa maombi 100 kwa sekunde. Gharama zinatofautiana kulingana na aina ya swali; huu si ufikiaji usio na kikomo. Hifadhi ufunguo wa hiari katika `OPENALEX_API_KEY`. Tumia `per_page` (upeo 100) na uwekaji kurasa wa kielekezi (cursor pagination).
- Crossref ina ufikiaji wa metadata ya umma wenye udhibiti wa kasi. Mahusiano ya masasisho na ishara za Retraction Watch zinahitaji ukaguzi wa DOI na mwelekeo; kukosekana kwa rekodi hakuthibitishi kuwa makala haijaathiriwa.
- Unpaywall inahitaji barua pepe halisi ya mawasiliano katika `UNPAYWALL_EMAIL`. Kukosekana kwa eneo la faili hakuthibitishi kuwa hakuna nakala ya ufikiaji wazi (OA).
- arXiv, Europe PMC, PubMed E-utilities na DOAJ ni vyanzo vya ziada vyenye sera zake mahususi. Si vyote vinavyojaribiwa na majaribio chaguo-msingi. Semantic Scholar ina mipaka ya pamoja ya matumizi bila kujitambulisha na mipaka tofauti ya funguo za API; ufikiaji hauhakikishi upatikanaji wa muktadha wa nukuu.
- Scite, Dimensions, Scopus, Web of Science na bidhaa za kutambua maandishi ya AI ni huduma za nje za hiari. Kagua haki za akaunti na API pamoja na viwango vya matumizi kabla ya kutumia; hakuna ahadi ya mpango wa bure kwa wote au bei maalum.

Angalia [uthibitishaji wa OpenAlex](https://help.openalex.org/api/authentication/), [bajeti na gharama za maswali](https://help.openalex.org/api/llm-quick-reference/), na [vichungi vya masasisho vya Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Upokeaji thabiti na kiini cha umma

Safu ya upokeaji wa mabaki ya utafiti hutoa `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, viunganishi (adapters) 15 (stadi 14 pamoja na hifadhi rudufu ya maandishi ghafi opaque fallback), na zana 12 za stdio MCP zisizohifadhi hali. Stakabadhi za upokeaji zinazokubaliwa hufunga kila mabadiliko ya kisemantiki yanayohifadhiwa kwa aina, utambulisho na SHA-256 sanifu: vitu vya utafiti, rekodi za CEG, rekodi za maamuzi, vipengele vinavyohitaji ukaguzi, stakabadhi halisi na usajili wa mabaki ya utafiti. Marudio ya hifadhi ya muda (cache replay) hukagua ahadi hizo bila kutegemea alama zaรหัส za picha ya usafirishaji. Kumbukumbu tupu ni halali; makundi ya miamala yanayoshindwa hayaachi hali nusu.

Mamlaka ya maudhui ya ufuatiliaji wa asili yanawekwa wazi nje ya mfumo mkuu. Wapigaji wa Python wanaoaminika hupitisha `LineageVerificationContext` wanaporudia stakabadhi au picha zilizohifadhiwa; wapigaji wa MCP wanaweza kutoa baiti za maudhui zenye ukomo pekee, na kamwe si mzizi wa mfumo wa faili wa kompyuta mwenyeji. Bajeti chaguo-msingi ya maudhui ni 10 MiB; mwenyeji anayeaminika anaweza kuruhusu waziwazi mabaki makubwa zaidi chini ya sera sawa ya mzalishaji na mthibitishaji. Bila mamlaka ya maudhui, dai lililowekwa `fully_verified` haliwezi kurudiwa kwa uhuru na hurudisha matokeo batili ya uthibitishaji yenye muundo maalum. Maandishi yasiyo na muundo yanabaki kama yalivyo, hoja kinzani zinabaki kuonekana wazi, na watafiti wanabaki na udhibiti wa kuhifadhi, kusitisha mwelekeo, kufungua upya, kuelekeza na kutoa maamuzi ya ukweli.

Angalia [usanifu wa kiini](../../docs/kernel-architecture.md) kwa mikataba na uoanifu. Vituo vya ukaguzi wa usambazaji na uchapishaji vimerekodiwa katika [mwongozo wa matoleo](../../docs/distribution-release.md). README za Kiingereza na Kichina Rahisi zimesawazishwa; hali za tafsiri nyingine zinaonyeshwa wazi katika [orodha ya ulandanishi](../../docs/i18n/manifest.json). Utambulisho wa mwisho wa toleo pendekezwa, CI ya HEAD kamili, mapitio ya jumla na ushahidi wa kuunganisha vimerekodiwa katika [kumbukumbu ya ufungaji](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Uthibitishaji

Tumia mazingira maalum ya Python. Maktaba za wakati wa utekelezaji zinategemea kazi mahususi na hazina uhakika wa kuwepo ndani ya Hermes. Programu tegemezi za QA ni pana zaidi ili mifano yote iliyowekwa alama iweze kuendeshwa:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

QA inathibitisha metadata, marejeleo, mifumo ya njia za kibinafsi au siri zinazojulikana, sintaksia ya Python na vizuizi vya msimbo vinavyotekelezeka vilivyowekwa alama. Kila mfano wa majaribio ya haraka (smoke) huendeshwa bila kubadilishwa katika mchakato mdogo mpya. Mifano ya michoro inakubali `PLOT_DIR` (chaguo-msingi ni `~/plots`, ikipanuliwa wazi); majaribio hutumia saraka ya muda. Vizuizi vya Python visivyoainishwa vinakataliwa; vizuizi vya `fragment:` vinakaguliwa sintaksia lakini vinahitaji ingizo lililotajwa na haviendeshwi peke yake. Vizuizi vya `external-test:` huendeshwa tu kupitia amri ya nje ya mwongozo. Inarudisha 0 ukaguzi uliosanidiwa ukifaulu, 1 kwa hitilafu ya msimbo/muundo/utambulisho, na 2 wakati mtandao/uthibitishaji/kiwango cha matumizi hakipatikani; huduma za hiari zisizosanidiwa zinabaki kuwa SKIP.

Majaribio yaliyofungwa ya uandishi wa stadi za Hermes yanatumiwa tena bila kubadilisha sheria zake za kila ujuzi. Ukaguzi wa idadi ya vifurushi vya usambazaji mzima wa juu hautumiki kwa tap hii; mfumo wetu wa majaribio unakagua stadi kumi na nne na kutatua marejeleo dhidi ya orodha iliyofungwa ya vifurushi vilivyomo na vya hiari. Hili si jaribio kamili la usakinishaji wa Hermes. CI hutumia mtandao kusakinisha programu tegemezi pekee; majaribio ya kawaida hayapigi simu API za kitaaluma.

CI huendesha kifurushi kamili cha QA kwenye Linux x86_64 (Python 3.10–3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 preview canary (ubuntu-26.04 na ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest), na macOS Intel (macos-15-intel), pamoja na uhakiki wa moja kwa moja wa canary dhidi ya tawi kuu la juu. Toleo pendekezwa la msingi lilifaulu majaribio 1165 ya ndani. Matokeo ya sasa ya marekebisho na mipaka ya upeo vimerekodiwa katika [marekebisho ya usahihi](../../docs/maintenance/correctness-repair-20261008.md); ushahidi wa mbali unatambulisha HEAD iliyojaribiwa tofauti. Mtiririko tofauti wa kuunganisha tap huendeshwa wakati msimbo unaposukumwa kwenye main: unasakinisha toleo la Hermes lililofungwa kwenye `tests/upstream/provenance.json` na kujaribu `tap add`, `search`, `install` na `list` dhidi ya hifadhi hii. Matoleo kamili, ukaguzi na vikwazo viko katika [ripoti ya ukaguzi](../../docs/project-lineage-audit-20260920.md).

Saraka ya [tools/longtail/](../../tools/longtail/README.md) inashikilia kizalishaji thabiti cha vipengele vya hali adimu (long-tail): wagombea 4096 waliotokana na mbegu ya SHA256, hali 30 zilizochaguliwa na ripoti ya upeo wa uthibitisho iliyokokotolewa kwa mashine. Muundo wa v3 unahesabu tofauti familia za uwezo (E01), stadi 14 halisi za hifadhi (E02), na malengo ya kazi (E03). Kila hali ina ujuzi mmoja wa msingi, lengo la kazi linaloungwa mkono na uwezo unaooana; kila ujuzi lazima uonekane angalau mara mbili chini ya malengo mawili tofauti, ikiwa ni pamoja na lengo lake kuu lililotangazwa. Mkengeuko wa saraka za ujuzi husababisha uthibitishaji kushindwa. Upanuzi wa kisemantiki (minyoro ya kazi, vigezo vya ukweli na uingizaji wa matukio yanayotekelezwa) unabaki kuwa hatua tofauti; upeo wa vipengele hauthibitishi upeo wa utekelezaji wa mtiririko wa kazi.

`scripts/scfabric/` ni safu ya utekelezaji wa zana za hesabu za kisayansi na takwimu: uchunguzi wa maunzi, orodha ya viendeshi yenye milango ya `dtype`, wasifu tano za mzigo wa kazi, vipimo vilivyooanishwa vyenye ukaguzi wa usawa wa namba, na `ComputeReceipt`. Vipimo vya duru ya kwanza kwenye mashine hii viko katika [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md); kanuni ya msingi ni kutumia CPU kwa chaguo-msingi, na kutumia kiongeza kasi (accelerator) pale tu kunapokuwa na stakabadhi.

## Fanya utafiti wa makala ukitumia Agent wa ndani

Sakinisha `academic-research-kernel[research]==2.2.0` na uhamishe mtiririko wa kazi uliofungashwa:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Acha Work au Agent wa ndani anayeoana asome faili hiyo ya `SKILL.md` iliyohamishwa, kisha uliza:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Toa tu DOI, kiungo cha umma au kifurushi cha faili za ndani. Kwa makala mbili, mwombe alinganishe data, mbinu, masharti ya tathmini na matokeo, akieleza ni nini kinachoweza kulinganishwa moja kwa moja. Agent anaendelea kupitia usomaji wa maandishi asilia, uhakiki wa sehemu zilizopendekezwa, ukokotoaji, upokeaji kwenye kiini, uzalishaji wa ripoti na uhakiki na uthibitisho huru wa vyanzo katika kazi hiyo hiyo. Uso uliopo wa MCP unabaki na zana zake 12; uratibu mpya unaishi kwenye CLI na ujuzi unaobebeka.

Hatua halisi za programu ni:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

Amri ya `prepare` inachukua na kuchambua nyenzo kuwa orodha ya faili (manifest), alama zaรหัส za chanzo na vipande vya maandishi vilivyopatikana. Amri ya `finish` inathibitisha uchimbaji uliozalishwa na Agent na kukokotoa upya madai yanayostahili ya t/p, ukubwa wa athari wa makundi mawili na hesabu/asilimia kwa kutumia zana zilizopo za takwimu, kisha inahifadhi hali ya kiini na ripoti za Kichina za Markdown/HTML. Amri ya `compare` inathibitisha tathmini ya wazi ya Agent kuhusu masharti yanayoweza kulinganishwa. Amri hizi hazipachiki muundo wa kudumu wa Work: usomaji wa kisemantiki unafanywa na Agent wa sasa akifuata [paper-research](../../skills/paper-research/SKILL.md). Faili asilia zilizohifadhiwa na picha za uchimbaji zinasaidia marudio thabiti ya nje ya mtandao. Upataji wa mtandao na usomaji mpya wa kisemantiki unabaki kuwa shughuli zinazotambulika tofauti.

## Usahihi wa 2.0.1 na uthibitishaji wa usambazaji

Toleo la bidhaa 2.0.1 linajumuisha marekebisho ya usahihi kwa ukokotoaji wa takwimu, ufuatiliaji wa kuondolewa kwa makala na udhibiti wa vipindi vya MCP. Zana ya umma ya `academic_recompute_statistics` inatoa thamani za p za kipimo cha t na Cohen's d / Hedges' g ya makundi mawili. Vipindi vya uaminifu (CI) na OR/RR vinabaki kuwa vitendakazi vya chini vya Python. Toa `p_value_literal` (kwa mfano `"1.0e-5"`) au `p_value_decimals` wakati usahihi wa desimali wa ripoti unapokuwa muhimu. Thamani za maandishi (literals) zinahifadhi sufuri za mwisho; ingizo la namba linahifadhi tu uwakilishi wake wa namba. Vyanzo vya usahihi vinavyopingana vinashindwa waziwazi. Ulinganishaji wa kukadiria nusu kwenda juu (round-half-up) unajumuisha mpaka wa chini wa makadirio na kuondoa mpaka wa juu. Kutofautiana kwa kawaida kwa takwimu ni matokeo halali ya kisayansi; ukokotoaji batili au ulioshindwa kwa sehemu unaweka alama ya `isError`.

Ukaguzi wa kuondolewa kwa machapisho (retraction) unarekodi uchunguzi wa sasa wa `True`/`False`/`unknown` tofauti na thamani ya mwisho iliyojulikana (`last-known`). Uhifadhi mfupi kabla ya swali unapanga uchunguzi wa DOI moja na kuhifadhi masasisho ya DOI nyingine. Uchunguzi wa sasa na uthibitisho wa kihistoria una matoleo tofauti: uthibitisho uliochelewa unaweza kuboresha historia iliyohifadhiwa huku hali mpya ya `unknown` ikibaki bila kuthibitishwa waziwazi kwa ukaguzi wa sasa. Data za majaribio za HTTP katika minyororo ya kurudia zimewekwa alama kama data ya majaribio.

MCP inajibu `ping`, inabaki kimya kwa arifa halali (ikiwa ni pamoja na `notifications/cancelled`), na inaweka kipindi cha stdio hai baada ya ingizo batili. Utekelezaji wa wakati mmoja hautangazi ughairi wa mapema (preemptive cancellation). Ushughulikiaji wa ujumbe unafuata [mkataba wa ujumbe wa MCP](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) na [vipimo vya ping](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Jenga na uthibitishe vifurushi vya usambazaji vya nakala hii kwa kutumia mazingira yaliyotengwa:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

Chaguo la `--source-checks` linafungua kifurushi pendekezwa cha `sdist` bila kukibadilisha nje ya hifadhi, linaweka `ARK_REPO` na `ARK_SDIST` kwenye kifurushi hicho, na kuendesha majaribio yake, QA tuli, vizuizi vya msimbo vinavyotekelezeka na ukaguzi wa i18n. Usakinishaji wa `wheel` na `sdist` kila mmoja hutumia mazingira mapya; `uvx` hutumia `wheel` ya ndani yenye hifadhi ya muda inayojitegemea. Ripoti inarekodi alama zaรหัส za vifurushi na njia zilizosakinishwa za kuingiza programu. Ukaguzi mwepesi uliopangwa wa Hermes unaripoti SHA iliyojaribiwa kwa matoleo yaliyofungwa (pinned) na ya hivi karibuni (latest) kwa kujitegemea. JSON ya mkataba wa nje na muhtasari wa kazi hutumia `healthy`, `degraded` na `failed`; vipimo vilivyorukwa vinabaki wazi.

## Nyaraka za utafiti na mipango

Nyaraka hizi mbili ni marejeleo ya uchunguzi wa mipango, si mpango kazi wa lazima. Namba zake za mwelekeo zinakokotolewa upya kutoka kwenye mpangilio uliohifadhiwa ndani ya `docs/direction-primitive-mapping.json`.

- [Atlasi ya Changamoto v0 (Kiingereza)](../../docs/pain-atlas-v0.en.md), [Toleo la Kichina](../../docs/pain-atlas-v0.zh.md): sehemu zenye changamoto katika mzunguko wa maisha ya kazi ya maarifa ya kitaaluma, pamoja na hali za uthibitishaji zilizoambatishwa kwenye madai ya kiasi.
- [Mpango wa Utafiti v0 (Kiingereza)](../../docs/research-plan-v0.en.md), [Toleo la Kichina](../../docs/research-plan-v0.zh.md): muundo wa Research Object, nyanja za uwezo wa msingi, mielekeo inayopendekezwa na jedwali la mtengano wa vipengele la awamu ya kwanza.
