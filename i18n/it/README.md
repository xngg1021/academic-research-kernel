# academic-research-kernel (it)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Nucleo neutro per la ricerca accademica e suite di deliberazione multi-agente. Fornisce 13 competenze accademiche e strumenti di verifica con punti di ingresso portabili Agent Plugins v1 e MCP (Model Context Protocol), nonché integrazione nativa per Hermes Agent, Claude Code, Cursor e subagenti CLI.

Autore: Junfu Shi (SJF, xngg1021), Hermes Agent. Licenza: [Source Lineage License 1.0](../../LICENSE).

## Licenza

Questa versione adotta la **Source Lineage License 1.0** per il materiale coperto specificato in [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Gli snapshot storici fino a `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` mantengono la licenza MIT originale.

## Competenze

| Competenza | Versione | Descrizione |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Verifica incrociata dell'identità e del conteggio delle citazioni; controllo di aggiornamenti e ritrattazioni; reperimento testi OA e verifica PDF |
| `skills/literature-analysis` | 1.3.0 | Dodici flussi di lavoro: similarità tematica, sovrapposizione testuale, contro-evidenze, profili autori, simulazione revisione e verifica fallacie |
| `skills/academic-writing` | 1.1.1 | Redazione e revisione accademica, linee guida per le citazioni (ISO 690, APA, MLA, Chicago, IEEE, AMA e profili regionali) e norme per gli autori |
| `skills/math-computation` | 1.2.1 | Instradamento per domini matematici e statistici con ricette numeriche; file di riferimento avanzati |
| `skills/quantitative-paper-audit` | 1.1.0 | Ricalcolo delle statistiche riportate (dimensione dell'effetto, valori p, intervalli di confidenza, OR/RR) e rilevamento discrepanze |
| `skills/research-reproducibility` | 1.0.1 | Pipeline di audit della riproducibilità in 14 fasi con checklist strutturate e registri riproducibili |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Log di ricerca PRISMA, screening della letteratura, conversione della dimensione dell'effetto, eterogeneità e pooling |
| `skills/literature-watch` | 1.1.0 | Monitoraggio settimanale: tracciamento di argomenti, autori e citazioni di DOI su OpenAlex e Crossref senza duplicati |
| `skills/retraction-watch` | 1.1.0 | Monitoraggio settimanale: ricontrollo degli elenchi di DOI rispetto a registri di ritrattazione e aggiornamenti Crossref |
| `skills/research-object-identity` | 1.1.0 | Identificazione deterministica delle risorse di ricerca e tracciamento della provenienza con convalida del DAG causale |
| `skills/claim-evidence-graph` | 1.0.0 | Collegamento deterministico tra asserzioni scientifiche, evidenze e provenienza computazionale |
| `skills/decision-ledger` | 1.0.0 | Registro delle Decisioni di Ricerca: log deterministico e di solo accodamento di decisioni, esiti negativi e stato dei percorsi |
| `skills/cross-review-five` | 2.0.0 | Orchestrazione dinamica di panel multi-revisore per modelli eterogenei con assegnazione di Kuhn-Munkres e deliberazione sparsa v2 |

## Standard Accademici e Baseline Multi-Profilo

Il repository stabilisce **ISO 690:2021** (Riferimenti bibliografici), **ISO 5127:2017** (Fondamenti e vocabolario) e **W3C PROV** (Modello di provenienza) come baseline internazionali, accanto a profili regionali e standard di settore (APA 7th, IEEE, PRISMA 2020, ICMJE). Consultare l'[Architettura degli Standard](../../docs/standards/README.md) e la [Guida Terminologica](../../docs/terminology/README.md).

## Integrazione e utilizzo portatile

```bash
python scripts/mcp_server.py
```

## Validazione e CI

La CI esegue l'intera suite QA su Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 e macOS Intel, con 625 test unitari superati e validazione canary upstream in tempo reale.

## Documenti di Ricerca e Pianificazione

- [Atlante delle Criticità v0 (Inglese)](../../docs/pain-atlas-v0.en.md), [Versione Cinese](../../docs/pain-atlas-v0.zh.md): Punti di attrito nel ciclo di lavoro accademico con verifica delle fonti.
- [Piano di Ricerca v0 (Inglese)](../../docs/research-plan-v0.en.md), [Versione Cinese](../../docs/research-plan-v0.zh.md): Modello Research Object, aree di competenza principali e matrice di scomposizione fattoriale.
