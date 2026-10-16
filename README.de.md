# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

Umgebungsunabhängiges, deterministisches Werkzeugset zur Verwaltung und Verifikation wissenschaftlicher Forschungszustände in agentengestützten Arbeitsabläufen. Über eine deterministische Erfassung von Forschungsartefakten und einen universellen Model-Context-Protocol-Server (MCP) verbindet es Forschungsobjekt-Identifikation, empirische Evidenz- und Prüfnachweise, Verknüpfungen von Aussagen und Belegen sowie ein fortschreibbares Protokoll zu Forschungsentscheidungen und Fehlversuchen. 14 spezialisierte wissenschaftliche Skills fungieren als Erzeuger und Konsumenten verifizierter Forschungszustände und bieten native Unterstützung für Claude Code, Cursor, Codex, Gemini CLI und Hermes Agent. Validierungsumfang und Einschränkungen externer Dienste sind im [Audit](docs/project-lineage-audit-20260920.md) dokumentiert.

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Aktueller Lizenzumfang: [Source Lineage License 1.0](LICENSE).

## Schnellstart

Version 2.1.0 mit [uv](https://docs.astral.sh/uv/getting-started/installation/) starten:

```bash
uvx academic-research-kernel@2.1.0 mcp
```

Das [Release 2.1.0](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0) verzeichnet die Distributions-Hashes und den Veröffentlichungsstatus. Das Release-Wheel lässt sich auch lokal mit `uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp` ausführen. Unterstützt wird Python 3.10–3.14; `uvx --python 3.12` wählt explizit einen unterstützten Interpreter. Alle 12 deterministischen Werkzeuge einschließlich der Statistikfunktionen sind in der Basisinstallation enthalten.

## Installation prüfen

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

Die Offline-Diagnose überprüft Abhängigkeiten, Schemata und alle 12 Werkzeugdefinitionen. Optionale externe Dienste müssen dafür nicht konfiguriert sein. Für maschinenlesbare Ausgaben steht `doctor --json` bereit.

## Paketinstallation

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Alternativ kann die Installation mit `pipx install academic-research-kernel==2.1.0` oder innerhalb einer unterstützten virtuellen Umgebung über `python -m pip install academic-research-kernel==2.1.0` erfolgen. `[full]` ergänzt Bibliotheken für erweiterte wissenschaftliche Berechnungsbeispiele; `[qa]` installiert Repository-Validierungswerkzeuge einschließlich des PDF-Parsers. `[research]` fügt `pypdf==6.19.0` und `fonttools==4.65.0` für eine konsistente PDF-Schriftdekodierung auf frischen Installationen hinzu (beide unterstützen Python 3.10). Das Lesen von strukturiertem HTML/XML sowie größenbegrenzten DOCX/XLSX-Dateien nutzt die Standardbibliothek. GPU-Backends und kostenpflichtige Dienste bleiben optional.

## Hermes

Stellen Sie sicher, dass `uv` im Prozess-PATH von Hermes liegt, und installieren sowie aktivieren Sie anschließend das portable Plugin explizit:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

Der bestehende Bezeichner `academic-skills` bleibt erhalten und umfasst nun 14 Skills einschließlich `paper-research`. Die `mcp.json` des Plugins ruft `uv run --frozen --no-dev --no-editable` mit Python 3.12 und der `uv.lock` des Checkouts auf; die Laufzeitumgebung liegt isoliert unter `${PLUGIN_DATA}/runtime`. Beim ersten Start werden Abhängigkeiten eingerichtet, ohne Python-Pakete von Hermes oder dem Hostsystem mitzubenutzen; zum Herunterladen fehlender Pakete oder Interpreter ist beim ersten Aufruf Netzwerkzugriff erforderlich. Der ältere, rein auf Skills beschränkte Tap wird weiterhin unterstützt (siehe den Abschnitt zu Integration und portablem Einsatz unten).

## Aus dem Quellcode ausführen

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Hinweise zur Klassifizierung der Abhängigkeiten, zur Reproduktion, zur Release-Identität, zu Veröffentlichungsprüfpunkten und zum Validierungsumfang finden Sie unter [Distribution und Release](docs/distribution-release.md).

## Lizenz

Der Snapshot mit diesem Hinweis wendet die **Source Lineage License 1.0** auf das abgedeckte Material und die in [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) benannten Rechte an. Der erste SLL-Commit mit Baum sowie der spätere grenzaufzeichnende Commit sind in [LICENSE-HISTORY.md](LICENSE-HISTORY.md) und [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) unterschieden. Snapshots ab diesem aufgezeichneten Übergang, die diesen Hinweis behalten, tragen denselben Lizenzumfang.

Historische Snapshots bis einschließlich `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` standen unter MIT-Lizenz, vorbehaltlich der für diese Kopien geltenden Bedingungen. Empfänger behalten gültige MIT-Rechte und müssen nicht zu SLL migrieren. Der [frühere MIT-Text des Projekts](LICENSES/MIT-pre-SLL.txt) bleibt erhalten; [tests/upstream/LICENSE](tests/upstream/LICENSE) und dessen Fremdherkunft bleiben unverändert. Das neue Wurzelangebot löscht diese Rechte nicht.

SLL erlaubt weitgehend Nutzung, Studium, Änderung, kommerzielle Nutzung, Verbreitung und proprietäre Ergänzungen, vorbehaltlich der anwendbaren Lizenz-, Hinweis- und Herkunftsbedingungen. Es ist kein Copyleft und verlangt keine Quelloffenlegung. Ein reiner Netzdienst ohne Bereitstellung von Kopien löst die Kern-Dienst-Herkunftshinweisbedingung für sich allein nicht aus. Es gibt keine ausdrückliche Patentgewährung. Fremdmaterial unterliegt weiterhin seinen eigenen Bedingungen. Maßgeblich ist der englische Originaltext der [LICENSE](LICENSE); `LicenseRef-Source-Lineage-1.0` ist eine lokale Referenz, keine SPDX-Zuweisung, und es wird keine OSI-Anerkennung beansprucht. Die [Beitragsannahme](CONTRIBUTING.md) ist von nachgelagerten Lizenzberechtigungen getrennt.

## Skills

| Skill | Version | Funktion |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Identität und quellenspezifische Zitationszahlen gegenprüfen; Aktualisierungs-/Rücknahmesignale prüfen; OA-Text auffinden und PDF-Identität verifizieren |
| `skills/literature-analysis` | 1.3.0 | Zwölf Workflows: Themenähnlichkeit, lokale Textüberschneidung, Gegenbeweise, Autorenprofile, Probegutachten, Fehlschlussprüfung, Review-Matrix, Zeitschriftenkandidaten, BibTeX, zweisprachiges Lesen, Forschungslücken-Screening, Reproduktion |
| `skills/academic-writing` | 1.1.1 | Lektorat, Zitierrichtlinien (ISO 690, APA, MLA, Chicago, IEEE, AMA sowie regionale Profile), Zeitschriftenhinweise, optionale Prüfdienste, Einreichungsunterlagen und institutionelle Anforderungen |
| `skills/math-computation` | 1.2.1 | Bestehendes Domänen-/Aufgaben-Routing mit korrigierten numerischen und statistischen Beispielen; vier domänenspezifische Referenzdateien |
| `skills/quantitative-paper-audit` | 1.1.0 | Berichtete Statistiken neu berechnen (Effektgröße, p-Werte, Konfidenzintervalle, OR/RR, erreichte Power) und numerische Abweichungen erkennen |
| `skills/research-reproducibility` | 1.0.1 | Vierzehnstufige Reproduktionsaudit-Pipeline mit strukturierter Checkliste, fünf Faktenstufen und reproduzierbaren Audit-Nachweisen |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA-Suchprotokolle, Screening-Protokolle, Effektgrößenkonversion, Heterogenität, gepoolte feste/zufällige Effekte, Sensitivitäts- und Publikationsbias-Diagnostik |
| `skills/literature-watch` | 1.1.0 | Wöchentlicher Blueprint: Themen, Autoren und DOI-zitierende Werke auf OpenAlex und Crossref überwachen; deduplizieren und nur Neues melden |
| `skills/retraction-watch` | 1.1.0 | Wöchentlicher Blueprint: DOI-Beobachtungsliste gegen OpenAlex `is_retracted` und Crossref-Aktualisierungsdatensätze (`update-to`-Signale) erneut prüfen; nur Statusänderungen melden |
| `skills/research-object-identity` | 1.1.0 | Deterministische Forschungsobjekt-Identifikation und Provenienz / Nachvollziehbarkeit: Identifikator-Normalisierung, 5-Zustände-Prüfung, inhaltsadressierter Ableitungsgraph, kausale DAG-Validierung und Offline-Rückverfolgung in unter 100 ms |
| `skills/claim-evidence-graph` | 1.0.0 | Deterministische Verknüpfung von Aussagen und Belegen: Verbindung wissenschaftlicher Behauptungen, empirischer Evidenz-/Prüfnachweise und rechnerischer Provenienz |
| `skills/decision-ledger` | 1.0.0 | Protokoll zu Forschungsentscheidungen und Fehlversuchen: deterministisches, nur fortschreibbares Protokoll für Forschungsentscheidungen, Fehlversuche (negative Ergebnisse), Routenstatus / Warum diese Route beendet wurde und Ergebniskorrekturen |
| `skills/paper-research` | 1.0.0 | Lesen von DOI-, URL- oder lokalen Papern samt Anhängen mit validierten Feldkandidaten, statistischen Nachprüfungen, persistentem Forschungszustand, quellengebundenen chinesischen Berichten und Zwei-Paper-Vergleich |
| `skills/cross-review-five` | 2.0.0 | Dynamische Multi-Reviewer-Panel-Orchestrierung für beliebige Modelle und Subagenten (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini usw.): v2 Sparse-Deliberation-Pipeline mit ungarischer Kuhn-Munkres-Zuordnung, Aussagen-Clustering, gezielter anonymer Hinterfragung und P0–P3-Schweregraden |

Die vierzehn Skills umfassen 22 Markdown-Referenzdateien, die nur bei Bedarf geladen werden.

## Wissenschaftliche Standards & Multi-Profil-Architektur

Zitierstile, Berichtsrichtlinien und Metadatenspezifikationen hängen von der jeweiligen Zeitschrift, Förderorganisation, Disziplin und Rechtsprechung ab. Das Repository etabliert **ISO 690:2021** (Bibliografische Referenzen), **ISO 5127:2017** (Information und Dokumentation – Vokabular) und **W3C PROV** (Provenienz-Datenmodell) als internationale Baselines, ergänzt durch regionale Profile (z. B. DIN ISO 690:2021 in Deutschland, GB/T 7714-2025 in Festlandchina, UNE-ISO 690:2024 in Spanien) sowie Fachstandards (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Die Vorgaben des Zielpublikationsorgans haben stets Vorrang vor Standardprofilen. Details siehe [Scholarly Standards Architecture](docs/standards/README.md) und [Terminologie-Leitfaden](docs/terminology/README.md).

Version 2.1.0 validiert die Konsistenz von DOI- und Ressourcenidentifikatoren, wechselseitig ausschließende quantitative Prüfflags sowie den gemeinsamen Vertrag für offene Prüfpunkte zwischen Kernel und Prüfnachweisen. Die Vollständigkeit des Caches wird unabhängig von den Änderungslisten eines Prüfnachweises aus den gespeicherten Quell-Envelopes und normalisierten Bindungen rekonstruiert; das gleichzeitige Entfernen eines Eintrags und seiner Cache-Deklaration führt daher zu keinem akzeptierten Replay. Siehe den [Abschlussbericht der vier Blocker](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Integration & Portabler Einsatz

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
Dieses Repository entspricht der herstellerneutralen Spezifikation **Agent Plugins v1** (`plugin.json`) und stellt zentrale akademische Verifikations- und statistische Neuberechnungswerkzeuge über einen stdio-**MCP-Server** (`mcp.json` / `scripts/mcp_server.py`) bereit. Kompatibel mit Claude Code, Cursor, Gemini CLI und jedem modernen Agenten-Framework. (Hinweis: Während die Repository-Identität `academic-research-kernel` lautet, bleiben der Plugin-Manifestname `academic-skills` und die MCP-Konfigurationsaliase aus Gründen der Abwärtskompatibilität stabil.)

```bash
# Als stdio-MCP-Server in Ihrer Agentenumgebung hinzufügen
uvx academic-research-kernel mcp
```

### 2. Native Installation in Hermes
In einer Hermes-Installation:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Die übrigen Skills installiert man durch Ersetzen des Verzeichnisnamens im vollständigen Bezeichner. Ein normaler Tap liest den Standardzweig, sodass ein frischer Tap den obigen Skillsatz installiert. Um einen Arbeitszweig vor dem Merge zu prüfen, diesen Zweig lokal auschecken und die lokalen Ordner-Anweisungen der installierten Hermes-Version befolgen. Nicht annehmen, dass der Tap-Befehl automatisch einen Pull-Request-Zweig auswählt.

Gebündelte verwandte Skills, geprüft gegen Upstream `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video. huggingface-hub und llama-cpp liegen im optionalen Katalog und müssen gegebenenfalls installiert werden. ocr-and-documents und pc-hardware-benchmark waren in diesem Snapshot nicht enthalten und sind keine Abhängigkeiten. Sitzungswerkzeuge sowie Dokument-/Browser-Backends hängen von der lokalen Konfiguration ab.

## Datenquellenzugriff

- OpenAlex-Basisabfragen laufen anonym mit kleinerem Tagesbudget. Die Dokumentation vom 2026-09-06 nennt 0,10 USD/Tag anonym und 1 USD/Tag mit kostenlosem API-Schlüssel, dazu ein Limit von 100 Anfragen/Sekunde. Kosten unterscheiden sich nach Abfragetyp; dies ist kein unbegrenzter Zugang. Ein optionaler Schlüssel liegt in `OPENALEX_API_KEY`. `per_page` (maximal 100) und Cursor-Pagination verwenden.
- Crossref bietet öffentlichen Metadatenzugriff mit Drosselung. Aktualisierungsbeziehungen und Retraction-Watch-Signale erfordern DOI-/Richtungsprüfungen; fehlende Datensätze beweisen nicht, dass ein Paper unbetroffen ist.
- Unpaywall erfordert eine echte Kontakt-E-Mail in `UNPAYWALL_EMAIL`. Ein fehlender Standort beweist nicht, dass keine OA-Kopie existiert.
- arXiv, Europe PMC, PubMed E-utilities und DOAJ sind ergänzende Quellen mit eigenen Richtlinien. Sie werden nicht alle von den Standardtests aufgerufen. Semantic Scholar hat gemeinsame anonyme Limits und separat zugewiesene Schlüssellimits; Zugriff garantiert keine Verfügbarkeit des Zitatkontexts.
- Scite, Dimensions, Scopus, Web of Science und KI-Erkennungsprodukte sind optionale externe Dienste. Vor der Nutzung aktuelle Konto-/API-Berechtigungen und Kontingente prüfen; eine allgemeine Gratisstufe oder Festpreise werden nicht zugesagt.

Siehe [OpenAlex-Authentifizierung](https://help.openalex.org/api/authentication/), [Budgets/Abfragekosten](https://help.openalex.org/api/llm-quick-reference/) und [Crossref-Aktualisierungsfilter](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Deterministische Erfassung und öffentliche Kernel-Schnittstelle

Version 2.1.0 stellt `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 Adapter (die 14 Skills sowie ein Opaque-Fallback) und 12 zustandslose stdio-MCP-Werkzeuge bereit. Akzeptierte Erfassungsnachweise binden jede gespeicherte semantische Änderung nach Typ, Identität und kanonischem SHA-256: Forschungsobjekte, Verknüpfungen von Aussagen und Belegen, Einträge im Protokoll zu Forschungsentscheidungen und Fehlversuchen, offene Prüfpunkte, physische Prüfnachweise sowie Artefaktregistrierungen. Das Cache-Replay überprüft diese Bindungen unabhängig von den Hashwerten der Transportsnapshots. Leere Protokolle sind gültig; fehlgeschlagene atomare Batches hinterlassen keinen Teilzustand.

Die Berechtigung zum Lesen von Provenienzinhalten wird explizit außerhalb des Bandes erteilt. Vertrauenswürdige Python-Aufrufer übergeben `LineageVerificationContext` beim Replay serialisierter Prüfnachweise oder Snapshots; MCP-Aufrufer dürfen nur begrenzte Inhaltsbytes übergeben, niemals ein Dateisystem-Stammverzeichnis des Hosts. Das Standardbudget für Inhalte beträgt 10 MiB; ein vertrauenswürdiger Host kann größere Artefakte unter derselben Erzeuger-/Prüfer-Richtlinie explizit autorisieren. Ohne Inhaltsautorisierung kann eine `fully_verified`-Aussage nicht unabhängig reproduziert werden und liefert ein strukturiertes ungültiges Prüfergebnis. Unstrukturierter Text bleibt opak, abweichende Bewertungen bleiben sichtbar, und Forschende behalten die Kontrolle über Commits, das Beenden oder Wiederaufnehmen von Routen, das Routing sowie fachliche Urteile.

Siehe [die Kernel-Architektur](docs/kernel-architecture.md) für Verträge und Kompatibilität. Distributions- und Veröffentlichungsprüfpunkte sind im [Release-Leitfaden](docs/distribution-release.md) dokumentiert. Die englische und die vereinfachte chinesische README sind aktuell synchronisiert; der Status weiterer Übersetzungen wird im [Manifest](docs/i18n/manifest.json) ausgewiesen. Finale Kandidatenidentität, exakte HEAD-CI, kumulative Reviews und Merge-Nachweise sind im [Abschlussprotokoll](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342) festgehalten.

## Validierung

Eine dedizierte Python-Umgebung verwenden. Laufzeitbibliotheken sind aufgabenspezifisch und nicht garantiert in Hermes installiert. Die QA-Abhängigkeiten sind breiter gefasst, damit alle markierten Beispiele ausgeführt werden können:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

QA prüft Metadaten, Referenzen, Muster für persönliche Pfade und bekannte Geheimnisse, Python-Syntax und markierte ausführbare Codeblöcke. Jedes Smoke-Beispiel läuft unverändert in einem frischen Subprozess. Plot-Beispiele akzeptieren `PLOT_DIR` (Standard `~/plots`, explizit expandiert); Tests nutzen ein temporäres Verzeichnis. Nicht klassifizierte Python-Codeblöcke werden abgelehnt; `fragment:`-Blöcke werden syntaxgeprüft, benötigen aber benannte Eingaben und laufen nicht eigenständig. `external-test:`-Blöcke laufen nur über den manuellen externen Befehl. Rückgabe: 0 bei bestandenen konfigurierten Prüfungen, 1 bei Code-/Schema-/Identitätsfehlern, 2 bei Transport-/Authentifizierungs-/Kontingentunverfügbarkeit; optionale, nicht konfigurierte Dienste bleiben SKIP.

Die gepinnten Hermes-Authoring-Tests werden ohne Änderung ihrer Pro-Skill-Regeln wiederverwendet. Upstream-Prüfungen über die Gesamtverteilung gelten für diesen Tap nicht; unsere Testumgebung prüft vierzehn Skills und löst Referenzen gegen den gepinnten gebündelten/optionalen Katalog auf. Dies ist kein vollständiger Hermes-Installationstest. CI nutzt das Netzwerk nur zur Installation von Abhängigkeiten; reguläre Tests rufen keine Wissenschafts-APIs auf.

CI führt die vollständige QA-Suite auf Linux x86_64 (Python 3.10–3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 Preview-Canary (ubuntu-26.04 & ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest) und macOS Intel (macos-15-intel) mit laufender Upstream-Canary-Validierung aus. Der historische Baseline-Kandidat bestand 1165 lokale Tests; aktuelle Reparaturergebnisse und Abdeckungsgrenzen sind in [der Korrektheitsreparatur](docs/maintenance/correctness-repair-20261008.md) dokumentiert, wobei Remote-Nachweise den getesteten HEAD separat ausweisen. Ein separater Tap-Integrations-Workflow läuft bei Pushes auf main: Er installiert den gepinnten Hermes-Checkout aus tests/upstream/provenance.json und führt tap add, search, install und list gegen dieses Repository aus. Exakte Versionen, Prüfungen und Einschränkungen stehen im [Audit](docs/project-lineage-audit-20260920.md).

[tools/longtail/](tools/longtail/README.md) enthält den deterministischen Long-Tail-Faktorgenerator: 4096 SHA256-initiierte Kandidaten, 30 ausgewählte Szenarien und einen maschinenberechneten Prüfabdeckungsbericht. Das v3-Modell zählt Fähigkeitsfamilien (E01), die 14 tatsächlichen Repository-Skills (E02) und Aufgabenziele (E03) getrennt. Jedes Szenario besitzt genau einen primären Skill, ein unterstütztes Aufgabenziel und kompatible Fähigkeiten; jeder Skill muss mindestens zweimal unter zwei verschiedenen Zielen erscheinen, einschließlich seines deklarierten Kernziels. Abweichungen im Skill-Verzeichnis führen zum Fehlschlagen der Validierung. Die semantische Erweiterung (Aufgabenketten, Orakel und ausgeführte Ereignisinjektion) bleibt eine separate Stufe; Faktorabdeckung beweist keine Workflow-Ausführungsabdeckung.

scripts/scfabric/ bildet die Ausführungsschicht für wissenschaftliche Berechnungs- und Statistikwerkzeuge: Hardware-Sonde, Backend-Katalog mit Dtype-Schranken, fünf Auslastungsprofile, gepaarte Benchmarks mit Paritätsprüfung und ComputeReceipt. Erste Messungen auf dieser Maschine finden sich in [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md); als Faustregel gilt standardmäßig CPU und ein Beschleuniger nur mit entsprechendem Prüfnachweis.

## Paper-Analyse mit einem lokalen Agenten

Installieren Sie `academic-research-kernel[research]==2.1.0` und exportieren Sie den mitgelieferten Workflow:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Lassen Sie Work oder einen kompatiblen lokalen Agenten diese exportierte `SKILL.md` lesen und fragen Sie anschließend:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Übergeben Sie lediglich die DOI, einen öffentlichen Link oder ein lokales Dateipaket. Bei zwei Papern bitten Sie den Agenten, Daten, Methoden, Evaluationsbedingungen und Ergebnisse zu vergleichen und zu erläutern, was direkt vergleichbar ist. Der Agent führt innerhalb derselben Aufgabe das Lesen des Originaltexts, die Kandidatenvalidierung, die Nachberechnung, die Erfassung, die Berichtserstellung und die unabhängige Quellenprüfung durch. Die bestehende MCP-Oberfläche behält ihre 12 Werkzeuge; die neue Orchestrierung liegt in der CLI und im portablen Skill.

Die tatsächlichen Programmphasen lauten:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` bezieht und parst das Material in ein Manifest, Quell-Hashes und lokalisierte Textsegmente. `finish` validiert eine vom Agenten erzeugte Extraktion, berechnet geeignete t/p-Werte, Zwei-Gruppen-Effektgrößen sowie Anzahl-/Prozentangaben mit den vorhandenen Statistikwerkzeugen neu und speichert anschließend den Kernel-Zustand sowie chinesische Markdown-/HTML-Berichte. `compare` validiert die explizite Bewertung vergleichbarer Bedingungen durch den Agenten. Diese Befehle betten kein residentes Work-Modell ein: Das semantische Lesen übernimmt der aktuelle Agent anhand von [paper-research](skills/paper-research/SKILL.md). Gespeicherte Originaldateien und Extraktions-Snapshots unterstützen ein deterministisches Offline-Replay. Netzwerkerfassung und ein neues semantisches Lesen bleiben getrennt ausgewiesene Operationen.

## 2.0.1 Korrektheits- und Distributionsprüfung

Seit Produktversion 2.0.1 stellt das öffentliche Werkzeug `academic_recompute_statistics` p-Werte für t-Tests sowie Cohen's d / Hedges' g für zwei Gruppen bereit; Konfidenzintervalle (CI) und OR/RR bleiben Python-Funktionen auf niedrigerer Ebene. Übergeben Sie `p_value_literal` (beispielsweise `"1.0e-5"`) oder `p_value_decimals`, wenn die berichtete Genauigkeit relevant ist. Literale erhalten nachfolgende Nullen; numerische Eingaben bewahren nur ihre numerische Darstellung. Widersprüchliche Genauigkeitsangaben schlagen explizit fehl. Kaufmännische Rundungsvergleiche (round-half-up) schließen die untere Rundungsgrenze ein und die obere Grenze aus. Eine gewöhnliche numerische Abweichung ist ein reguläres wissenschaftliches Prüfergebnis; ungültige oder teilweise fehlgeschlagene Berechnungen setzen `isError`.

Rücknahmeprüfungen zeichnen die aktuelle Beobachtung (`True` / `False` / `unknown`) getrennt vom zuletzt bekannten Wert auf. Eine kurze Vorab-Reservierung ordnet Beobachtungen derselben DOI und bewahrt Aktualisierungen anderer DOIs. Aktuelle Beobachtungen und historische Bestätigungen führen getrennte Versionen: Eine verspätet eintreffende Bestätigung kann die gespeicherte Historie ergänzen, während ein neueres `unknown` für die aktuelle Prüfung explizit als unbestätigt erhalten bleibt. HTTP-Fixtures in den Regressionsketten sind als Testdaten gekennzeichnet.

MCP antwortet auf `ping`, bleibt bei gültigen Benachrichtigungen (einschließlich `notifications/cancelled`) stumm und hält die stdio-Sitzung nach ungültigen Eingaben aufrecht. Die synchrone Implementierung kündigt keinen präemptiven Abbruch an. Die Nachrichtenverarbeitung folgt dem [MCP-Nachrichtenvertrag](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) und der [Ping-Spezifikation](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Erstellen und verifizieren Sie die Distributionspakete dieses Checkouts in einer isolierten Umgebung:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` entpackt das Kandidaten-sdist unverändert außerhalb des Checkouts, setzt `ARK_REPO` und `ARK_SDIST` auf diesen Kandidaten und führt dessen Tests, die statische QA, ausführbare Codeblöcke sowie die i18n-Prüfung aus. Wheel- und sdist-Installationen nutzen jeweils eine frische Umgebung; `uvx` verwendet das lokale Wheel mit einem unabhängigen Cache. Der Bericht verzeichnet Artefakt-Hashes und die tatsächlichen Importpfade. Geplante leichtgewichtige Hermes-Prüfungen (gepinnt/aktuell) melden den getesteten SHA separat. Externe Vertrags-JSONs und Job-Zusammenfassungen nutzen `healthy`, `degraded` und `failed`; übersprungene Sonden bleiben explizit ausgewiesen.

## Forschungs- und Planungsdokumente

Diese beiden Dokumente dienen als explorative Planungsreferenzen und stellen keine verbindliche Roadmap dar. Ihre Richtungsnummern werden aus der gespeicherten Gruppierung in docs/direction-primitive-mapping.json neu berechnet.

- [Pain Atlas v0 (Englisch)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md): Reibungspunkte im Lebenszyklus akademischer Wissensarbeit, mit Verifikationszustand für quantitative Aussagen.
- [Forschungsplan v0 (Englisch)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md): Research-Object-Modell, Kernfähigkeitsbereiche, Kandidatenrichtungen und die Faktorzerlegungsmatrix der ersten Phase.
