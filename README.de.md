# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

Harness-neutraler akademischer Forschungskern und Deliberations-Suite für Multi-Agenten-Systeme. Er bietet 13 wissenschaftliche Skills und Verifikationstools mit portablen Agent Plugins v1- und MCP-Einstiegspunkten sowie nativer Integration für Hermes Agent, Claude Code, Cursor und benutzerdefinierte CLI-Subagenten. Das Repository enthält ausführbare Beispielprüfungen; Validierungsumfang und Einschränkungen externer Dienste sind im [Audit](docs/project-lineage-audit-20260920.md) dokumentiert.

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Aktueller Lizenzumfang: [Source Lineage License 1.0](LICENSE).

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
| `skills/retraction-watch` | 1.1.0 | Wöchentlicher Blueprint: DOI-Beobachtungsliste gegen OpenAlex is_retracted und Crossref-Aktualisierungsdatensätze (update-to-Signale) erneut prüfen; nur Statusänderungen melden |
| `skills/research-object-identity` | 1.1.0 | Deterministische Forschungsobjekt-Identifikation und Provenienz / Nachvollziehbarkeit: Identifikator-Normalisierung, 5-Zustände-Urteil, inhaltsadressierter Ableitungsgraph, kausale DAG-Validierung und Offline-Rückverfolgung |
| `skills/claim-evidence-graph` | 1.0.0 | Verknüpfung von Aussagen und Belegen: wissenschaftliche Behauptungen, empirische Evidenznachweise und rechnerische Herkunft |
| `skills/decision-ledger` | 1.0.0 | Protokoll zu Forschungsentscheidungen und Fehlversuchen: deterministisches Protokoll für Forschungsentscheidungen, Fehlversuche, Gründe für Routenbeendigungen und Ergebniskorrekturen |
| `skills/cross-review-five` | 2.0.0 | Dynamisches Multi-Reviewer-Panel für heterogene Modelle und Subagenten (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini usw.): v2 4-Stufen Sparse-Deliberation-Pipeline mit Kuhn-Munkres-Ungarischer Zuordnung und P0-P3-Schweregraden |

Die dreizehn Skills umfassen 21 Markdown-Referenzdateien, die nur bei Bedarf geladen werden.

## Wissenschaftliche Standards & Multi-Profil-Architektur

Zitierstile, Berichtsrichtlinien und Metadatenspezifikationen hängen von der jeweiligen Zeitschrift, Förderorganisation, Disziplin und Rechtsprechung ab. Das Repository etabliert **ISO 690:2021** (Referenzen und Zitate), **ISO 5127:2017** (Information und Dokumentation - Vokabular) und **W3C PROV** (Provenienz-Datenmodell) als internationale Baselines, ergänzt durch regionale Profile (z. B. DIN ISO 690:2021 in Deutschland, GB/T 7714-2025 in Festlandchina, UNE-ISO 690 in Spanien) sowie Fachstandards (APA, IEEE, PRISMA 2020, ICMJE). Die Vorgaben der Zielinstitution haben stets Vorrang. Details siehe [Scholarly Standards Architecture](docs/standards/README.md) und [Terminologie-Leitfaden](docs/terminology/README.md).

## Integration & Installation

### 1. Agent Plugins v1 & MCP-Server
Dieses Repository entspricht der herstellerneutralen Spezifikation **Agent Plugins v1** (`plugin.json`) und stellt grundlegende akademische Verifikations- und statistische Neuberechnungstools über einen stdio **MCP-Server** (`mcp.json` / `python scripts/mcp_server.py`) bereit. Kompatibel mit Claude Code, Cursor, Gemini CLI und modernen Agenten-Frameworks.

```bash
# Als stdio-MCP-Server in Ihrer Agentenumgebung hinzufügen
python scripts/mcp_server.py
```

### 2. Installation in Hermes

Die aktuelle Upstream-Tap-Erkennung prüft unmittelbare Unterverzeichnisse von `skills/`. Jeder Skill liegt daher direkt unter diesem Stamm. In einer Hermes-Installation:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Die übrigen Skills installiert man durch Ersetzen des Verzeichnisnamens im vollständigen Bezeichner. Ein normaler Tap liest den Standardzweig, sodass ein frischer Tap den obigen Skillsatz installiert. Um einen Arbeitszweig vor dem Merge zu prüfen, diesen Zweig lokal auschecken und die lokalen Ordner-Anweisungen der installierten Hermes-Version befolgen. Nicht annehmen, dass der Tap-Befehl einen PR-Zweig auswählt.

Gebündelte verwandte Skills, geprüft gegen Upstream `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video. huggingface-hub und llama-cpp liegen im optionalen Katalog und müssen gegebenenfalls installiert werden. ocr-and-documents und pc-hardware-benchmark waren in diesem Snapshot nicht enthalten und sind keine Abhängigkeiten. Sitzungswerkzeuge sowie Dokument-/Browser-Backends hängen von der lokalen Konfiguration ab.

## Datenquellenzugriff

- OpenAlex-Basisabfragen laufen anonym mit kleinerem Tagesbudget. Die Dokumentation vom 2026-09-06 nennt 0,10 USD/Tag anonym und 1 USD/Tag mit kostenlosem API-Schlüssel, dazu ein Limit von 100 Anfragen/Sekunde. Kosten unterscheiden sich nach Abfragetyp; dies ist kein unbegrenzter Zugang. Ein optionaler Schlüssel liegt in `OPENALEX_API_KEY`. `per_page` (maximal 100) und Cursor-Pagination verwenden.
- Crossref bietet öffentlichen Metadatenzugriff mit Drosselung. Aktualisierungsbeziehungen und Retraction-Watch-Signale erfordern DOI-/Richtungsprüfungen; fehlende Datensätze beweisen nicht, dass ein Paper unbetroffen ist.
- Unpaywall erfordert eine echte Kontakt-E-Mail in `UNPAYWALL_EMAIL`. Ein fehlender Standort beweist nicht, dass keine OA-Kopie existiert.
- arXiv, Europe PMC, PubMed E-utilities und DOAJ sind ergänzende Quellen mit eigenen Richtlinien. Sie werden nicht alle von den Standardtests aufgerufen. Semantic Scholar hat gemeinsame anonyme Limits und separat zugewiesene Schlüssellimits; Zugriff garantiert keine Verfügbarkeit des Zitatkontexts.
- Scite, Dimensions, Scopus, Web of Science und KI-Erkennungsprodukte sind optionale externe Dienste. Vor der Nutzung aktuelle Konto-/API-Berechtigungen und Kontingente prüfen; eine allgemeine Gratisstufe oder Festpreise werden nicht zugesagt.

Siehe [OpenAlex-Authentifizierung](https://help.openalex.org/api/authentication/), [Budgets/Abfragekosten](https://help.openalex.org/api/llm-quick-reference/) und [Crossref-Aktualisierungsfilter](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Validierung

Eine dedizierte Python-Umgebung verwenden. Laufzeitbibliotheken sind aufgabenspezifisch und nicht garantiert in Hermes installiert. Die QA-Abhängigkeiten sind breiter, damit alle markierten Beispiele laufen:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA prüft Metadaten, Referenzen, Muster für persönliche Pfade/bekannte Geheimnisse, Python-Syntax und markierte ausführbare Zäune. Jedes Smoke-Beispiel läuft unverändert in einem frischen Subprozess. Plot-Beispiele akzeptieren `PLOT_DIR` (Standard `~/plots`, explizit expandiert); Tests nutzen ein temporäres Verzeichnis. Nicht klassifizierte Python-Zäune werden abgelehnt; `fragment:`-Blöcke werden syntaxgeprüft, benötigen aber benannte Eingaben und laufen nicht eigenständig. `external-test:`-Blöcke laufen nur über den manuellen externen Befehl. Rückgabe: 0 bei bestandenen konfigurierten Prüfungen, 1 bei Code-/Schema-/Identitätsfehlern, 2 bei Transport-/Authentifizierungs-/Kontingentunverfügbarkeit; optionale, nicht konfigurierte Dienste bleiben SKIP.

Die gepinnten Hermes-Authoring-Tests werden ohne Änderung ihrer Pro-Skill-Regeln wiederverwendet. Upstream-Prüfungen über die Gesamtverteilung gelten für diesen Tap nicht; unser Harness prüft dreizehn Skills und löst Referenzen gegen den gepinnten gebündelten/optionalen Katalog auf. Dies ist kein vollständiger Hermes-Installationstest. CI nutzt das Netzwerk nur zur Installation von Abhängigkeiten; gewöhnliche PR-Tests rufen keine Wissenschafts-APIs auf.

CI führt die vollständige QA-Suite per GitHub Actions auf Linux x86_64 (Python 3.10-3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 Preview-Canary (ubuntu-26.04 und ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest) und macOS Intel (macos-15-intel) über alle Plattformen und Architekturen aus, mit 703 bestandenen Unit-Tests und kontinuierlicher Upstream-Canary-Validierung. Ein separater Tap-Integrations-Workflow läuft bei Push auf main: Er installiert den gepinnten Hermes-Checkout aus tests/upstream/provenance.json und führt tap add, search, install und list gegen dieses Repository aus. Exakte Versionen, Prüfungen und Einschränkungen stehen im [Audit](docs/project-lineage-audit-20260920.md).

tools/longtail/ enthält den deterministischen Generator für extreme Long-Tail-Szenarien: 4096 SHA256-initiierte Kandidatenkombinationen über entkoppelte Faktorenachsen, gierige Abdeckungsauswahl und der maschinenberechnete Abdeckungsbericht in generated-scenarios.json.

scripts/scfabric/ ist das wissenschaftliche Rechen-Fabric: Hardware-Sonde, Backend-Katalog mit Dtype-Gates, fünf Auslastungsprofile, gepaarte Benchmarks mit Paritätsprüfung und ComputeReceipt. Messungen befinden sich in [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md).

## Forschungs- und Planungsdokumente

- [Pain Atlas v0 (Englisch)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md): Reibungspunkte im Lebenszyklus akademischer Wissensarbeit, mit Verifikationszustand für quantitative Aussagen.
- [Forschungsplan v0 (Englisch)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md): Research-Object-Modell, Kernfähigkeitsbereiche, Kandidatenrichtungen und die Faktorzerlegungsmatrix der ersten Phase.
