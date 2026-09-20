# academic-research-kernel (it)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Nucleo neutro per la ricerca accademica e suite di deliberazione multi-agente. Fornisce 13 competenze accademiche e strumenti di verifica con punti di ingresso portatili Agent Plugins v1 e MCP (Model Context Protocol), oltre all'integrazione nativa per Hermes Agent, Claude Code, Cursor e sub-agenti CLI personalizzati. Copre verifica delle fonti, analisi della letteratura, scrittura accademica, calcolo numerico, audit quantitativo di articoli, audit di riproducibilità, revisione sistematica e meta-analisi, identità e provenienza degli oggetti di ricerca, orchestrazione dinamica della revisione incrociata tra modelli e due automazioni di monitoraggio settimanale. Il repository include controlli eseguibili di esempio; l'ambito di validazione e le limitazioni dei servizi esterni sono documentati nell'[audit](../../docs/project-lineage-audit-20260920.md).

Autore: Junfu Shi (SJF, xngg1021), Hermes Agent. Offerta con ambito attuale: [Source Lineage License 1.0](../../LICENSE).

## Licenza

Lo snapshot contenente questo avviso adotta la **Source Lineage License 1.0** per il Materiale Coperto e i diritti identificati in [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Il primo commit e albero SLL, e il successivo commit di registrazione del confine, sono distinti in [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) e [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Gli snapshot successivi che conservano questo avviso mantengono la medesima offerta.

Gli snapshot storici fino a `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` erano concessi in licenza con MIT. I destinatari conservano autorizzazioni MIT valide e non devono migrare a SLL. Il [testo MIT precedente del progetto](../../LICENSES/MIT-pre-SLL.txt) è conservato; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) e la provenienza di terze parti rimangono invariati. La nuova offerta radice non cancella tali diritti.

La SLL consente ampiamente l'uso, lo studio, la modifica, l'uso commerciale, la distribuzione e aggiunte proprietarie, subordinate alle condizioni applicabili di licenza, avviso e lignaggio della fonte. Non è copyleft e non richiede la divulgazione del codice sorgente. Il servizio di rete puro senza fornitura di copie non attiva da solo la condizione di avviso di lignaggio del servizio Core. Non vi è alcuna concessione esplicita di brevetti. Il testo esatto inglese di [LICENSE](../../LICENSE) disciplina questo riepilogo; `LicenseRef-Source-Lineage-1.0` è un riferimento locale, non un'assegnazione SPDX. L'[accettazione dei contributi](../../CONTRIBUTING.md) è separata dai permessi di licenza a valle.

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

Ci sono 21 file di riferimento Markdown nelle tredici competenze. I riferimenti vengono caricati solo quando necessario.

## Standard Accademici e Baseline Multi-Profilo

Stili di citazione, criteri di rendicontazione e contratti di metadati dipendono dalla rivista di destinazione, dall'istituzione, dall'ente finanziatore, dalla disciplina e dalla giurisdizione. Il repository stabilisce **ISO 690:2021** (Riferimenti bibliografici), **ISO 5127:2017** (Vocabolario di informazione e documentazione) e **W3C PROV** (Modello di dati di provenienza) come standard internazionali, insieme a profili regionali e norme disciplinari (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). I requisiti della sede target hanno la precedenza sui profili predefiniti. Consultare l'[Architettura degli Standard](../../docs/standards/README.md) e la [Guida alla Terminologia Naturale](../../docs/terminology/README.md).

## Integrazione e Utilizzo Portatile

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
Questo repository è conforme alla specifica neutrale **Agent Plugins v1** (`../../plugin.json`) ed espone strumenti di verifica accademica e ricalcolo statistico tramite un **server MCP** stdio (`../../mcp.json` / `python scripts/mcp_server.py`). Compatibile con Claude Code, Cursor, Gemini CLI e qualsiasi moderno framework per agenti.

```bash
# Add as stdio MCP server in your agent harness
python scripts/mcp_server.py
```

### 2. Installazione Nativa in Hermes
Da un'installazione di Hermes eseguire:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Installare le altre competenze sostituendo il nome della directory nell'identificatore completo. Un normale tap legge il ramo predefinito. Competenze correlate verificate al commit `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video.

## Accesso alle Fonti Dati

- Le query di base di OpenAlex possono essere eseguite anonimamente con un budget giornaliero limitato ($0.10/giorno anonimo e $1/giorno con chiave API gratuita, tetto di 100 req/s). Memorizzare la chiave facoltativa in `OPENALEX_API_KEY`.
- Crossref fornisce accesso pubblico ai metadati con limitazione di frequenza. I segnali di aggiornamento e di Retraction Watch richiedono controlli DOI.
- Unpaywall richiede un'email di contatto reale in `UNPAYWALL_EMAIL`.
- arXiv, Europe PMC, PubMed e DOAJ sono fonti supplementari con proprie politiche. Scite, Dimensions, Scopus e Web of Science sono servizi esterni facoltativi.

## Validazione

Utilizzare un ambiente Python dedicato. Le dipendenze QA coprono tutti i controlli eseguibili:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

Il QA convalida metadati, riferimenti, percorsi personali/segreti noti, sintassi Python e blocchi di codice contrassegnati. Restituisce 0 in caso di successo, 1 per errori di codice/schema/identità e 2 per indisponibilità di trasporto/autenticazione/quota.

La CI esegue la suite completa di test su Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview, Windows x86_64, Windows ARM64, macOS ARM64 e macOS Intel, con 713 test unitari superati e 40 blocchi di codice eseguibili validati.

tools/longtail/ contiene il generatore deterministico di scenari estremi di coda lunga: 4096 combinazioni candidate con seed SHA256 su assi di fattori disaccoppiati, selezione vorace della copertura e report in generated-scenarios.json.

scripts/scfabric/ è la struttura di calcolo scientifico: sonda hardware, catalogo backend con filtri dtype, cinque profili di carico di lavoro e ComputeReceipt. Misurazioni registrate in [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md).

## Documenti di Ricerca e Pianificazione

Questi documenti sono riferimenti di pianificazione esplorativa, non una roadmap vincolante.

- [Atlante delle Criticità v0 (Inglese)](../../docs/pain-atlas-v0.en.md), [Versione Cinese](../../docs/pain-atlas-v0.zh.md): Punti di attrito nel ciclo di lavoro della conoscenza accademica con stati di verifica.
- [Piano di Ricerca v0 (Inglese)](../../docs/research-plan-v0.en.md), [Versione Cinese](../../docs/research-plan-v0.zh.md): Modello Research Object, aree di competenza chiave e matrice di scomposizione dei fattori.
