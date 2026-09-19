# academic-research-kernel (sw)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Kiini kisichoegemea upande wowote cha utafiti wa kitaaluma na mashauriano ya mawakala wengi. Hutoa ujuzi 13 wa kitaaluma na zana za uthibitishaji na maingizo ya Agent Plugins v1 na MCP (Model Context Protocol), pamoja na muunganisho wa asili kwa Hermes Agent, Claude Code, Cursor, na mawakala wadogo wa CLI.

Mwandishi: Junfu Shi (SJF, xngg1021), Hermes Agent. Leseni: [Source Lineage License 1.0](../../LICENSE).

## Leseni

Toleo hili linatumia **Source Lineage License 1.0** kwa nyenzo zilizobainishwa katika [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Matoleo ya kihistoria yaliyopita chini ya leseni ya MIT yanaendelea kutumika.

## Ujuzi wa Kitaaluma

| Ujuzi | Toleo | Maelezo |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Uthibitishaji mtambuka wa utambulisho na idadi ya nukuu; ukaguzi wa masasisho na ufutaji wa machapisho; upatikanaji wa maandishi wazi na uthibitishaji wa PDF |
| `skills/literature-analysis` | 1.3.0 | Mifumo kumi na miwili ya kazi: mfanano wa mada, mwingiliano wa maandishi, ushahidi kinzani, wasifu wa waandishi, majaribio ya mapitio na ukaguzi wa hoja |
| `skills/academic-writing` | 1.1.1 | Uhariri wa kitaaluma, mwongozo wa unukuu (ISO 690, APA, MLA, Chicago, IEEE, AMA na maelezo mafupi ya kikanda) na sheria za majarida |
| `skills/math-computation` | 1.2.1 | Uelekezaji wa hesabu na takwimu kupitia mbinu za kihesabu; faili za marejeleo ya juu |
| `skills/quantitative-paper-audit` | 1.1.0 | Ukokotoaji upya wa takwimu zilizoripotiwa (ukubwa wa athari, viwango vya p, vipindi vya kuaminika, OR/RR) na utambuzi wa kutofautiana |
| `skills/research-reproducibility` | 1.0.1 | Mchakato wa hatua 14 wa ukaguzi wa uwezo wa kurudia matokeo wenye orodha zilizopangwa na rekodi thabiti |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Kumbukumbu za utafutaji za PRISMA, uchujaji wa maandiko, ubadilishaji wa ukubwa wa athari, na uchambuzi meta |
| `skills/literature-watch` | 1.1.0 | Ufuatiliaji wa kila wiki: fuatilia mada, waandishi na nukuu za DOI kwenye OpenAlex na Crossref bila marudio |
| `skills/retraction-watch` | 1.1.0 | Ufuatiliaji wa kila wiki: kagua upya orodha ya DOI dhidi ya kumbukumbu za ufutaji na masasisho ya OpenAlex na Crossref |
| `skills/research-object-identity` | 1.1.0 | Utambulisho wa uhakika wa rasilimali za utafiti na ufuatiliaji wa asili wenye uthibitisho wa DAG ya kisababishi |
| `skills/claim-evidence-graph` | 1.0.0 | Uunganishaji thabiti wa madai ya kisayansi na rekodi za ushahidi pamoja na asili ya kimahesabu |
| `skills/decision-ledger` | 1.0.0 | Kumbukumbu ya Maamuzi ya Utafiti: rekodi thabiti ya kuongeza tu ya maamuzi ya utafiti, matokeo hasi na hali ya njia |
| `skills/cross-review-five` | 2.0.0 | Uratibu thabiti wa jopo la wakaguzi wengi kwa mifano mbalimbali kwa kutumia ugawaji wa Kuhn-Munkres na majadiliano ya v2 |

## Viwango vya Kitaaluma na Mwongozo wa Kimataifa

Hifadhi hii inaweka **ISO 690:2021** (Marejeleo ya kibibliografia), **ISO 5127:2017** (Msingi na msamiati), na **W3C PROV** (Muundo wa data wa asili) kama misingi ya kimataifa, sambamba na viwango vya kitaalamu (APA 7th, IEEE, PRISMA 2020, ICMJE). Tazama [Muundo wa Viwango](../../docs/standards/README.md) na [Mwongozo wa Istilahi](../../docs/terminology/README.md).

## Muunganisho na Matumizi Yanayohamishika

```bash
python scripts/mcp_server.py
```

## Uthibitishaji na CI

CI huendesha majaribio kamili ya QA kwenye mifumo ya Linux x86_64, Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows, na macOS, kukiwa na majaribio 625 ya vitengo yaliyofaulu na uthibitishaji wa moja kwa moja.

## Nyaraka za Utafiti na Mipango

- [Ramani ya Changamoto v0 (Kiingereza)](../../docs/pain-atlas-v0.en.md), [Toleo la Kichina](../../docs/pain-atlas-v0.zh.md): Changamoto katika mzunguko wa kazi za kitaaluma.
- [Mpango wa Utafiti v0 (Kiingereza)](../../docs/research-plan-v0.en.md), [Toleo la Kichina](../../docs/research-plan-v0.zh.md): Muundo wa Research Object, nyanja za uwezo wa msingi, na matriki ya uchambuzi wa vipengele.
