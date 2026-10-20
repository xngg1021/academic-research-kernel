# academic-research-kernel (it)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Sistema deterministico per la gestione dello stato della ricerca e la verifica metodologica nei flussi di lavoro scientifici assistiti da agenti, indipendente dall'ambiente di esecuzione. Unifica l'identità degli oggetti di ricerca, il documento di prova / verifica empirica, il collegamento tra affermazioni ed evidenze (CEG) e il registro delle decisioni di ricerca e dei tentativi falliti in modalità di sola aggiunta, tramite l'acquisizione di artefatti di ricerca e un server universale Model Context Protocol (MCP). Quattordici competenze scientifiche specializzate operano come produttori e consumatori dello stato di ricerca verificato, con supporto nativo per Claude Code, Cursor, Codex, Gemini CLI e Hermes Agent. L'ambito di validazione e i limiti dei servizi esterni sono documentati nell'[audit del progetto](../../docs/project-lineage-audit-20260920.md).

Autore: Junfu Shi (SJF, xngg1021), Hermes Agent. Offerta di licenza attuale: [Source Lineage License 1.0](../../LICENSE).

## Avvio rapido

Eseguire la versione 2.2.0 con [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx academic-research-kernel@2.2.0 mcp
```

La [release 2.2.0](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.2.0) riporta gli hash di distribuzione e lo stato di pubblicazione. Il pacchetto wheel di rilascio può essere eseguito anche localmente con `uvx --from ./academic_research_kernel-2.2.0-py3-none-any.whl academic-research-kernel mcp`. È supportato Python 3.10–3.14; `uvx --python 3.12` seleziona esplicitamente un interprete compatibile. Tutti i 12 strumenti deterministici, inclusi i moduli statistici, sono compresi nell'installazione di base.

## Verifica dell'installazione

```bash
uvx academic-research-kernel@2.2.0 doctor
uvx academic-research-kernel@2.2.0 --version
```

La diagnostica offline controlla dipendenze, schemi e le definizioni di tutti i 12 strumenti. I servizi esterni facoltativi possono restare non configurati. Utilizzare `doctor --json` per ottenere un output leggibile dalle macchine.

## Installazione del pacchetto

```bash
uv tool install academic-research-kernel==2.2.0
academic-research-kernel doctor
academic-research-kernel mcp
```

In alternativa, è possibile installare il pacchetto con `pipx install academic-research-kernel==2.2.0` oppure con `python -m pip install academic-research-kernel==2.2.0` all'interno di un ambiente virtuale supportato. L'opzione `[full]` aggiunge le librerie per gli esempi scientifici estesi; `[qa]` include gli strumenti di validazione del repository, compreso il parser PDF. L'opzione `[research]` aggiunge `pypdf==6.19.0` e `fonttools==4.65.0` per garantire una decodifica uniforme dei font PDF nelle installazioni pulite, entrambi compatibili con Python 3.10. La lettura strutturata di HTML/XML e di file DOCX/XLSX con limiti di dimensione utilizza la libreria standard. I backend GPU e i servizi a pagamento restano facoltativi.

## Hermes

Assicurarsi che `uv` sia presente nel `PATH` del processo Hermes, quindi installare e abilitare esplicitamente il plugin portatile:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

L'identità esistente `academic-skills` viene mantenuta per compatibilità e comprende 14 competenze, inclusa `paper-research`. Il file `mcp.json` del plugin invoca `uv run --frozen --no-dev --no-editable` con Python 3.12 e il file `uv.lock` del repository; l'ambiente isolato risiede in `${PLUGIN_DATA}/runtime`. Al primo avvio inizializza autonomamente le dipendenze senza attingere ai pacchetti Python di Hermes o del sistema operativo, richiedendo l'accesso di rete qualora manchino pacchetti o l'interprete. Il precedente metodo tap limitato alle sole competenze resta supportato nella sezione sull'utilizzo portatile riportata più avanti.

## Esecuzione dal codice sorgente

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Consultare [distribuzione e rilascio](../../docs/distribution-release.md) per la classificazione delle dipendenze, la riproduzione dei pacchetti, l'identità di rilascio, i controlli di pubblicazione e il perimetro di validazione.

## Licenza

Lo snapshot contenente questo avviso adotta la **Source Lineage License 1.0** per il Materiale Coperto e i diritti identificati in [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Il primo commit e albero SLL, così come il successivo commit di registrazione del confine, sono distinti in [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) e [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Gli snapshot successivi a tale transizione registrata che conservano questo avviso mantengono la medesima offerta con ambito definito.

Gli snapshot storici fino a `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` erano concessi sotto licenza MIT, secondo i termini applicabili a tali copie. I destinatari conservano i permessi MIT validi e non sono tenuti a migrare a SLL. Il [testo MIT precedente del progetto](../../LICENSES/MIT-pre-SLL.txt) è preservato; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) e la relativa provenienza di terze parti restano invariati. La nuova offerta alla radice non annulla tali diritti pregressi.

La SLL consente ampiamente l'uso, lo studio, la modifica, l'impiego commerciale, la distribuzione e le estensioni proprietarie, nel rispetto delle condizioni applicabili di licenza, avviso e lignaggio del codice sorgente. Non è copyleft e non impone la divulgazione del sorgente. L'erogazione di un puro servizio di rete senza fornitura di copie non attiva di per sé l'obbligo di avviso sul lignaggio del servizio Core. Non vi è alcuna concessione espressa di brevetti e il materiale di terze parti rimane soggetto alle proprie condizioni. Il testo originale in inglese di [LICENSE](../../LICENSE) prevale su questo riepilogo informativo; `LicenseRef-Source-Lineage-1.0` è un riferimento locale, non un identificatore SPDX, e non viene rivendicata alcuna approvazione OSI. L'[accettazione dei contributi](../../CONTRIBUTING.md) è separata dai permessi di licenza concessi a valle.

## Competenze

| Competenza | Versione | Funzione |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Verifica incrociata dell'identità bibliografica e dei conteggi delle citazioni per fonte; controllo dei segnali di aggiornamento o ritrattazione; individuazione dei testi Open Access e verifica dell'identità dei PDF |
| `skills/literature-analysis` | 1.3.0 | Dodici flussi di lavoro: similarità tematica, sovrapposizione testuale locale, contro-evidenze, profili degli autori, revisione simulata, controllo delle fallacie, matrice di revisione, riviste candidate, BibTeX, lettura bilingue, analisi delle lacune di ricerca e riproduzione |
| `skills/academic-writing` | 1.1.1 | Revisione editoriale accademica, guida agli stili di citazione (ISO 690, APA, MLA, Chicago, IEEE, AMA e profili regionali), istruzioni per gli autori, servizi opzionali di rilevamento, materiali di sottomissione e requisiti istituzionali |
| `skills/math-computation` | 1.2.1 | Instradamento per dominio e attività matematica con esempi numerici e statistici verificati; quattro file di riferimento specialistici |
| `skills/quantitative-paper-audit` | 1.1.0 | Ricalcolo delle statistiche riportate (dimensione dell'effetto, valori p, intervalli di confidenza, OR/RR, potenza statistica raggiunta) e rilevamento di discrepanze numeriche |
| `skills/research-reproducibility` | 1.0.1 | Pipeline di audit della riproducibilità in quattordici fasi con liste di controllo strutturate, cinque livelli di verifica fattuale e registri di audit riproducibili |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Log di ricerca PRISMA, registro di selezione della letteratura, conversione della dimensione dell'effetto, eterogeneità, sintesi a effetti fissi o casuali, analisi di sensibilità e diagnostica del bias di pubblicazione |
| `skills/literature-watch` | 1.1.0 | Monitoraggio settimanale: sorveglianza di argomenti, autori e opere citanti DOI su OpenAlex e Crossref, con deduplicazione e segnalazione delle sole novità |
| `skills/retraction-watch` | 1.1.0 | Monitoraggio settimanale: verifica periodica di una lista di DOI rispetto a `is_retracted` su OpenAlex e ai record di aggiornamento Crossref (segnali `update-to`), riportando solo le variazioni di stato |
| `skills/research-object-identity` | 1.1.0 | Identificazione deterministica delle risorse di ricerca e provenienza / tracciabilità: normalizzazione degli identificatori, verifica a cinque stati, grafi di derivazione indirizzati dal contenuto, convalida DAG causale e tracciamento del lignaggio in meno di 100 ms |
| `skills/claim-evidence-graph` | 1.0.0 | Definizione deterministica del collegamento tra affermazioni ed evidenze, connettendo asserzioni scientifiche, documenti di prova e provenienza computazionale |
| `skills/decision-ledger` | 1.0.0 | Registro delle decisioni di ricerca e dei tentativi falliti: log deterministico di sola aggiunta per scelte metodologiche, risultati negativi, stato del percorso / motivo dell'interruzione e revisioni degli esiti |
| `skills/paper-research` | 1.0.0 | Lettura di articoli e materiali supplementari tramite DOI, URL o file locali con convalida dei campi estratti, controlli statistici, stato di ricerca persistente, report in cinese collegati alle fonti e confronto tra due studi |
| `skills/cross-review-five` | 2.0.0 | Orchestrazione dinamica di panel multi-revisore compatibile con modelli e sub-agenti eterogenei (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini ecc.): pipeline Sparse Deliberation v2 con assegnazione ungherese di Kuhn-Munkres, clustering delle asserzioni, contestazione anonima mirata e classificazione di gravità P0–P3 |

Sono presenti 22 file di riferimento Markdown distribuiti tra le quattordici competenze, caricati esclusivamente quando necessario.

## Standard Accademici e Baseline Multi-Profilo

Gli stili di citazione, i criteri di rendicontazione scientifica e gli schemi di metadati dipendono dalla rivista di destinazione, dall'istituzione, dall'ente finanziatore, dalla disciplina e dalla giurisdizione. Il repository adotta **ISO 690:2021** (Riferimenti bibliografici), **ISO 5127:2017** (Vocabolario dell'informazione e della documentazione) e **W3C PROV** (Modello di dati per la provenienza) come riferimenti internazionali di base, affiancati da profili regionali (ad esempio GB/T 7714-2025 nella Cina continentale, UNE-ISO 690:2024 in Spagna, DIN ISO 690:2021 in Germania) e standard disciplinari (APA 7ª ed., IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Le norme specifiche della sede editoriale prevalgono sempre sui profili predefiniti. Consultare l'[Architettura degli Standard Accademici](../../docs/standards/README.md) e la [Guida alla Terminologia Naturale](../../docs/terminology/README.md).

Il consolidamento finale di integrità convalida la coerenza tra DOI e identificatori, l'esclusività dei flag booleani nei verdetti quantitativi e il contratto condiviso sugli elementi da verificare tra il nucleo e le ricevute di acquisizione. La completezza della cache viene ricostruita a partire dagli involucri sorgente conservati e dai legami normalizzati, indipendentemente dagli elenchi di mutazione della ricevuta; la rimozione simultanea di un record e della relativa dichiarazione di cache non può produrre una riproduzione accettata. Si veda il [resoconto di chiusura dei quattro blocchi](../../docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Integrazione e Utilizzo Portatile

### 1. Universal Agent Plugins v1 e Model Context Protocol (MCP)
Questo repository è conforme alla specifica indipendente dal fornitore **Agent Plugins v1** (`../../plugin.json`) ed espone gli strumenti principali di verifica bibliografica e ricalcolo statistico tramite un **server MCP** su stdio (`../../mcp.json` / `../../scripts/mcp_server.py`). È compatibile con Claude Code, Cursor, Gemini CLI e qualsiasi framework moderno per agenti. Sebbene l'identità del repository sia `academic-research-kernel`, il nome del manifesto `academic-skills` e gli alias di configurazione MCP restano invariati per garantire la retrocompatibilità.

```bash
# Add as stdio MCP server in your agent harness
uvx academic-research-kernel mcp
```

### 2. Installazione Nativa in Hermes
Da un'installazione di Hermes:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Per installare le altre competenze, sostituire il nome della directory nell'identificatore completo. Un normale comando tap legge il ramo predefinito del repository e installa il set di competenze elencato sopra. Per esaminare un ramo di lavoro prima dell'unione, eseguire il checkout locale di tale ramo e seguire le istruzioni di installazione da cartella locale previste dalla versione di Hermes installata, senza dare per scontato che il comando tap selezioni un ramo di revisione.

Competenze correlate verificate sullo snapshot upstream `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf e manim-video. I pacchetti huggingface-hub e llama-cpp appartengono al catalogo opzionale e possono richiedere un'installazione separata; ocr-and-documents e pc-hardware-benchmark non erano presenti in tale snapshot e non costituiscono dipendenze. Gli strumenti di sessione e i backend per documenti o browser dipendono dalla configurazione locale.

## Accesso alle Fonti Dati

- Le interrogazioni di base su OpenAlex possono essere eseguite in forma anonima con un budget giornaliero ridotto. Secondo la documentazione verificata il 2026-09-06, il limite è di 0,10 USD/giorno in modalità anonima e 1 USD/giorno con chiave API gratuita, oltre a un tetto di 100 richieste al secondo. I costi variano in base al tipo di query e non implicano accesso illimitato. Memorizzare l'eventuale chiave in `OPENALEX_API_KEY` e utilizzare `per_page` (massimo 100) con paginazione tramite cursore.
- Crossref fornisce accesso pubblico ai metadati con limitazione della frequenza di richiesta. Le relazioni di aggiornamento e i segnali di Retraction Watch richiedono controlli sul DOI e sulla direzione del legame; l'assenza di record non dimostra che un articolo sia esente da ritrattazioni o rettifiche.
- Unpaywall richiede un indirizzo email di contatto reale nella variabile `UNPAYWALL_EMAIL`. L'assenza di una posizione restituita non prova che non esista alcuna copia Open Access.
- arXiv, Europe PMC, PubMed E-utilities e DOAJ sono fonti complementari soggette a proprie politiche di utilizzo e non vengono tutte interrogate dai test predefiniti. Semantic Scholar applica limiti anonimi condivisi e quote separate per le chiavi API; l'accesso al servizio non garantisce la disponibilità del contesto di citazione.
- Scite, Dimensions, Scopus, Web of Science e i servizi di rilevamento di testo generato da IA sono integrazioni esterne facoltative. Verificare le abilitazioni dell'account, i diritti API e le quote disponibili prima dell'uso; non vengono garantiti livelli gratuiti universali né tariffe fisse.

Si vedano le guide su [autenticazione OpenAlex](https://help.openalex.org/api/authentication/), [budget e costi delle query](https://help.openalex.org/api/llm-quick-reference/) e [filtri di aggiornamento Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Acquisizione deterministica e nucleo pubblico

L'interfaccia di acquisizione mette a disposizione `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 adattatori (le 14 competenze più il fallback opaco) e 12 strumenti MCP stdio senza stato. Le ricevute di acquisizione accettate vincolano ogni mutazione semantica conservata per tipologia, identità e digest SHA-256 canonico: oggetti di ricerca, relazioni CEG, voci del registro delle decisioni di ricerca e dei tentativi falliti, elementi da verificare, ricevute fisiche e registrazioni di artefatti. La riproduzione da cache verifica tali impegni indipendentemente dagli hash degli snapshot di trasporto. I registri vuoti sono validi e i lotti atomici non riusciti non lasciano alcuno stato parziale.

L'autorità sui contenuti di lignaggio è esplicita e gestita fuori banda. I chiamanti Python attendibili passano `LineageVerificationContext` durante la riproduzione di ricevute o snapshot serializzati; i chiamanti MCP possono fornire byte di contenuto entro limiti prefissati, ma mai una radice del file system ospite. Il budget predefinito per i contenuti è di 10 MiB, con possibilità per un host fidato di autorizzare esplicitamente artefatti più grandi adottando la stessa politica tra produttore e verificatore. In assenza di autorità sul contenuto, un'affermazione `fully_verified` non può essere riprodotta autonomamente e restituisce un esito strutturato di verifica non valida. Il testo non strutturato rimane opaco, i dissensi restano visibili e i ricercatori mantengono il pieno controllo su conferme, interruzione o riapertura dei percorsi, instradamento e giudizi di validità scientifica.

Consultare l'[architettura del nucleo](../../docs/kernel-architecture.md) per i contratti formali e le regole di compatibilità. I punti di controllo per la distribuzione e la pubblicazione sono descritti nella [guida al rilascio](../../docs/distribution-release.md). I file README in inglese e cinese semplificato sono allineati alla versione corrente, mentre lo stato delle altre traduzioni è registrato nel [manifesto di sincronizzazione](../../docs/i18n/manifest.json). L'identità del candidato finale, l'esito della CI sull'esatto commit e le prove cumulative di revisione sono raccolti nel [registro di chiusura](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Validazione

Utilizzare un ambiente Python dedicato. Le librerie di esecuzione dipendono dal singolo compito e non sono necessariamente preinstallate in Hermes. Le dipendenze di QA sono più estese per consentire l'esecuzione di tutti gli esempi contrassegnati:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

La procedura di QA controlla metadati, riferimenti interni, pattern relativi a percorsi personali o segreti noti, sintassi Python e blocchi di codice eseguibili contrassegnati. Ogni esempio `smoke` viene eseguito senza modifiche in un sottoprocesso dedicato. Gli esempi grafici accettano `PLOT_DIR` (predefinito `~/plots`, espanso esplicitamente) e utilizzano una directory temporanea durante i test. I blocchi Python privi di classificazione vengono rifiutati; i blocchi `fragment:` sono sottoposti a verifica sintattica ma richiedono input nominati e non vengono eseguiti autonomamente. I blocchi `external-test:` vengono avviati solo tramite il comando manuale per le API esterne, che restituisce `0` al superamento dei controlli configurati, `1` in caso di errore di codice, schema o identità e `2` per indisponibilità di rete, autenticazione o quota, lasciando come `SKIP` i servizi opzionali non configurati.

I test di authoring fissati di Hermes vengono riutilizzati mantenendo invariate le regole per singola competenza. I controlli globali sull'intera distribuzione upstream non si applicano a questo repository; la suite locale verifica le quattordici competenze e risolve i riferimenti rispetto al catalogo fissato di componenti inclusi e opzionali, senza costituire un test completo dell'installazione di Hermes. La CI utilizza la rete esclusivamente per installare le dipendenze e i normali test di revisione non effettuano chiamate alle API accademiche.

La CI esegue l'intera suite di QA su Linux x86_64 (Python 3.10–3.14), Linux ARM64 (`ubuntu-24.04-arm`), Ubuntu 26.04 preview canary (`ubuntu-26.04` e `ubuntu-26.04-arm`), Windows x86_64, Windows ARM64 (`windows-11-arm`), macOS ARM64 (`macos-latest`) e macOS Intel (`macos-15-intel`), con validazione canary dal vivo rispetto al ramo principale upstream. La versione candidata storica ha superato 1165 test locali. I risultati attuali delle correzioni e i limiti di copertura sono documentati nel [rapporto sulle correzioni di accuratezza](../../docs/maintenance/correctness-repair-20261008.md), mentre le prove remote identificano separatamente il commit `HEAD` sottoposto a test. Un flusso separato di integrazione tap viene eseguito a ogni push su `main`, installando il checkout fissato di Hermes registrato in `tests/upstream/provenance.json` ed eseguendo `tap add`, `search`, `install` e `list` su questo repository. Versioni esatte, controlli e limitazioni sono riportati nell'[audit del progetto](../../docs/project-lineage-audit-20260920.md).

La directory [tools/longtail/](../../tools/longtail/README.md) contiene il generatore deterministico di fattori a coda lunga: 4096 candidati generati tramite seme SHA-256, 30 scenari selezionati e un rapporto di copertura della verifica calcolato automaticamente. Il modello v3 conteggia separatamente le famiglie di capacità (E01), le 14 competenze effettive del repository (E02) e gli obiettivi operativi (E03). Ogni scenario associa una competenza primaria, un obiettivo supportato e capacità compatibili; ciascuna competenza deve comparire almeno due volte sotto due obiettivi distinti, incluso il proprio obiettivo principale dichiarato. Qualsiasi disallineamento rispetto alle directory delle competenze determina il fallimento della validazione. L'espansione semantica (catene di compiti, oracoli e iniezione di eventi eseguiti) costituisce una fase distinta; la copertura dei fattori non dimostra di per sé la copertura di esecuzione dei flussi completi.

Il modulo `scripts/scfabric/` rappresenta l'infrastruttura per gli strumenti di calcolo scientifico e analisi statistica: rilevamento dell'hardware, catalogo dei backend con vincoli sui tipi di dati (`dtype`), cinque profili di carico, benchmark appaiato con ammissione basata sulla parità numerica e generazione di `ComputeReceipt`. Le misurazioni del primo ciclo sono raccolte in [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md); il criterio operativo prevede l'uso predefinito della CPU e l'attivazione degli acceleratori solo in presenza di una ricevuta verificata.

## Analizzare un articolo scientifico con un Agente locale

Installare `academic-research-kernel[research]==2.2.0` ed esportare il flusso di lavoro incluso nel pacchetto:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Far leggere il file `SKILL.md` esportato a Work o a un Agente locale compatibile, quindi chiedere:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
È sufficiente fornire il DOI, il link pubblico o la cartella locale dei documenti. Per confrontare due articoli, chiedere all'Agente di analizzare dati, metodi, condizioni di valutazione e risultati, specificando quali elementi siano direttamente comparabili. L'Agente eseguirà all'interno della medesima sessione la lettura del testo originale, la validazione dei campi estratti, il ricalcolo statistico, l'acquisizione nello stato del nucleo, la stesura del report e il controllo indipendente sulle fonti. La superficie MCP esistente conserva i suoi 12 strumenti, mentre la nuova orchestrazione è resa disponibile tramite la CLI e la competenza portatile.

Le fasi operative del programma sono:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

Il comando `prepare` acquisisce e analizza il materiale producendo un manifesto, gli hash dei file sorgente e i segmenti di testo localizzati. Il comando `finish` convalida l'estrazione strutturata prodotta dall'Agente e ricalcola i valori idonei di test t/valori p, dimensioni dell'effetto tra due gruppi e conteggi o percentuali mediante gli strumenti statistici esistenti, salvando poi lo stato del nucleo e i report in formato Markdown e HTML in lingua cinese. Il comando `compare` verifica la valutazione esplicita dell'Agente circa la comparabilità delle condizioni sperimentali. Questi comandi non incorporano un modello autonomo residente: la lettura semantica è svolta dall'Agente attivo seguendo le indicazioni di [paper-research](../../skills/paper-research/SKILL.md). I file originali salvati e gli snapshot di estrazione consentono la riproduzione deterministica offline, mantenendo l'acquisizione via rete e una nuova lettura semantica come operazioni distinte e tracciate separatamente.

## Correzioni della versione 2.0.1 e verifica della distribuzione

Il rilascio 2.0.1 integra le correzioni di accuratezza statistica e gestione del protocollo. Lo strumento pubblico `academic_recompute_statistics` espone i valori p dei test t e gli indici `d` di Cohen / `g` di Hedges per due gruppi, mentre gli intervalli di confidenza e i rapporti `OR/RR` rimangono disponibili come funzioni Python di livello inferiore. Quando la precisione riportata nell'articolo è determinante, fornire `p_value_literal` (ad esempio `"1.0e-5"`) oppure `p_value_decimals`. I valori letterali preservano gli zeri finali, mentre gli input numerici mantengono la sola rappresentazione numerica; fonti di precisione tra loro incompatibili generano un errore esplicito. I confronti con arrotondamento (`round-half-up`) includono l'estremo inferiore ed escludono quello superiore. Una normale discrepanza statistica costituisce un risultato scientifico valido, mentre calcoli non validi o parzialmente falliti impostano il flag `isError`.

I controlli sulle ritrattazioni registrano l'osservazione corrente (`True`/`False`/`unknown`) separatamente dall'ultimo valore noto. Una breve prenotazione prima della query ordina le osservazioni relative allo stesso DOI e preserva gli aggiornamenti sugli altri DOI. Le osservazioni correnti e le conferme storiche dispongono di versioni distinte: una conferma ricevuta in ritardo può aggiornare la cronologia conservata, mentre un esito `unknown` più recente resta esplicitamente contrassegnato come non verificato per il controllo corrente. Le risposte HTTP simulate nelle catene di test di regressione sono etichettate come dati di prova.

Il server MCP risponde a `ping`, rimane silenzioso alla ricezione di notifiche valide (inclusa `notifications/cancelled`) e mantiene attiva la sessione stdio anche dopo input non validi. L'implementazione sincrona non dichiara il supporto alla cancellazione preventiva. La gestione dei messaggi rispetta il [contratto dei messaggi MCP](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) e la [specifica di ping](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Per compilare e verificare i pacchetti di distribuzione di questo checkout in un ambiente isolato:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

L'opzione `--source-checks` estrae il pacchetto `sdist` candidato senza modifiche all'esterno della directory di lavoro, imposta `ARK_REPO` e `ARK_SDIST` su tale candidato ed esegue i test, i controlli statici di QA, i blocchi di codice eseguibili e la verifica di sincronizzazione i18n. Le installazioni da `wheel` e `sdist` avvengono ciascuna in un ambiente nuovo e indipendente, mentre `uvx` utilizza il file `wheel` locale con una cache separata. Il report finale registra gli hash degli artefatti e i percorsi effettivi di importazione. I controlli periodici leggeri su Hermes (`pinned` e `latest`) riportano separatamente lo SHA testato. I file JSON dei contratti esterni e i riepiloghi di esecuzione utilizzano gli stati `healthy`, `degraded` e `failed`, mantenendo esplicite le sonde ignorate.

## Documenti di ricerca e pianificazione

Questi due documenti rappresentano riferimenti esplorativi di pianificazione e non costituiscono una roadmap vincolante. La numerazione delle direzioni di ricerca viene ricalcolata a partire dal raggruppamento memorizzato in `docs/direction-primitive-mapping.json`.

- [Pain Atlas v0 (Inglese)](../../docs/pain-atlas-v0.en.md), [中文版](../../docs/pain-atlas-v0.zh.md): punti di criticità lungo il ciclo di vita del lavoro accademico, con stati di verifica associati alle affermazioni quantitative.
- [Research Plan v0 (Inglese)](../../docs/research-plan-v0.en.md), [中文版](../../docs/research-plan-v0.zh.md): il modello Research Object, le aree di competenza principali, le direzioni candidate e la matrice di scomposizione fattoriale della prima fase.
