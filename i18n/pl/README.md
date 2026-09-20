# academic-research-kernel (pl)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Neutralne jądro badań akademickich i zestaw wieloagentowej deliberacji. Zapewnia 13 umiejętności akademickich i narzędzi weryfikacyjnych z przenośnymi punktami wejścia Agent Plugins v1 i MCP (Model Context Protocol), a także natywną integrację dla Hermes Agent, Claude Code, Cursor i niestandardowych podagentów CLI. Obejmuje weryfikację źródeł, analizę literatury, pisanie akademickie, obliczenia numeryczne, audyt ilościowy publikacji, audyty odtwarzalności, przegląd systematyczny i metaanalizę, tożsamość i pochodzenie obiektów badawczych, dynamiczną orkiestrację wzajemnej recenzji oraz dwie cotygodniowe automatyzacje monitorowania. Repozytorium zawiera wykonywalne przykłady; zakres walidacji i ograniczenia usług zewnętrznych opisano w [audycie](../../docs/project-lineage-audit-20260920.md).

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Bieżąca oferta: [Source Lineage License 1.0](../../LICENSE).

## Licencja

Migawka zawierająca to powiadomienie przyjmuje **Source Lineage License 1.0** dla Materiału Objętego i praw określonych w [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Pierwszy commit i drzewo SLL oraz późniejszy commit rejestrujący granicę są rozróżnione w [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) i [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Migawki z tego zarejestrowanego przejścia zachowujące to powiadomienie niosą tę samą ofertę.

Historyczne migawki do `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` były objęte licencją MIT. Odbiorcy zachowują ważne uprawnienia MIT i nie muszą migrować do SLL. [Wcześniejszy tekst MIT projektu](../../LICENSES/MIT-pre-SLL.txt) został zachowany; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) i pochodzenie stron trzecich pozostają niezmienione. Nowa oferta główna nie unieważnia tych praw.

SLL szeroko zezwala na użycie, badanie, modyfikację, użycie komercyjne, dystrybucję i dodatki własnościowe pod warunkiem zachowania odpowiednich warunków licencji, powiadomienia i pochodzenia źródła. Nie jest to copyleft i nie wymaga ujawniania kodu źródłowego. Usługa sieciowa bez dostarczania kopii nie wyzwala sama z siebie warunku powiadomienia o pochodzeniu usługi Core. Nie ma wyraźnego udzielenia patentu. Ścisły angielski tekst [LICENSE](../../LICENSE) reguluje to podsumowanie informacyjne; `LicenseRef-Source-Lineage-1.0` jest referencją lokalną, a nie oznaczeniem SPDX. [Przyjmowanie wkładów](../../CONTRIBUTING.md) jest oddzielone od dalszych uprawnień licencyjnych.

## Umiejętności

| Umiejętność | Wersja | Opis |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Weryfikacja tożsamości i liczby cytowań; sprawdzanie aktualizacji i retrakcji; wyszukiwanie otwartego tekstu oraz weryfikacja plików PDF |
| `skills/literature-analysis` | 1.3.0 | Dwanaście procedur roboczych: podobieństwo tematów, nakładanie tekstu, kontrargumenty, profile autorów, symulacja recenzji i weryfikacja błędów logicznych |
| `skills/academic-writing` | 1.1.1 | Redakcja naukowa, wskazówki dotyczące cytowań (ISO 690, APA, MLA, Chicago, IEEE, AMA i profile regionalne) oraz wytyczne dla autorów |
| `skills/math-computation` | 1.2.1 | Przekierowywanie zadań matematycznych i statystycznych z gotowymi formułami numerycznymi; zaawansowane pliki referencyjne |
| `skills/quantitative-paper-audit` | 1.1.0 | Ponowne przeliczanie statystyk (wielkość efektu, wartości p, przedziały ufności, OR/RR) oraz wykrywanie rozbieżności liczbowych |
| `skills/research-reproducibility` | 1.0.1 | 14-etapowa ścieżka audytu powtarzalności ze ustrukturyzowanymi listami kontrolnymi i weryfikowalnymi raportami |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Protokoły wyszukiwania PRISMA, selekcja literatury, konwersja wielkości efektu, heterogeniczność i łączenie danych metaanalitycznych |
| `skills/literature-watch` | 1.1.0 | Cotygodniowy monitoring: śledzenie tematów, autorów i cytowań DOI w OpenAlex i Crossref z deduplikacją |
| `skills/retraction-watch` | 1.1.0 | Cotygodniowy monitoring: weryfikacja listy DOI pod kątem retrakcji i sygnałów aktualizacji w OpenAlex i Crossref |
| `skills/research-object-identity` | 1.1.0 | Deterministyczna identyfikacja zasobów badawczych i śledzenie pochodzenia z walidacją przyczynowego grafu DAG |
| `skills/claim-evidence-graph` | 1.0.0 | Deterministyczne łączenie twierdzeń naukowych, dowodów badawczych i obliczeniowego pochodzenia |
| `skills/decision-ledger` | 1.0.0 | Rejestr Decyzji Badawczych: deterministyczny, oparty na dopisywaniu rejestr decyzji, wyników negatywnych i statusu ścieżek badawczych |
| `skills/cross-review-five` | 2.0.0 | Dynamiczna orkiestracja wieloosobowego panelu recenzenckiego dla heterogenicznych modeli z algorytmem Kuhna-Munkresa i rzadką deliberacją v2 |

W trzynastu umiejętnościach znajduje się 21 plików referencyjnych Markdown. Referencje są ładowane tylko w razie potrzeby.

## Standardy Akademickie i Linia Bazowa Wieloprofilowa

Style cytowania, kryteria raportowania i kontrakty metadanych zależą od docelowego czasopisma, instytucji, fundatora, dyscypliny i jurysdykcji. Repozytorium ustanawia **ISO 690:2021** (Przypisy bibliograficzne), **ISO 5127:2017** (Słownictwo informacji i dokumentacji) oraz **W3C PROV** (Model danych proweniencji) jako międzynarodowe linie bazowe, obok profili regionalnych i standardów dyscyplinarnych (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Wymagania docelowego miejsca publikacji mają pierwszeństwo przed profilami domyślnymi. Zobacz [Architekturę Standardów](../../docs/standards/README.md) i [Przewodnik po Terminologii Naturalnej](../../docs/terminology/README.md).

## Integracja i Przenośne Użycie

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
To repozytorium jest zgodne z neutralną specyfikacją **Agent Plugins v1** (`../../plugin.json`) i udostępnia podstawowe narzędzia weryfikacji akademickiej oraz ponownego przeliczania statystycznego za pośrednictwem **serwera MCP** stdio (`../../mcp.json` / `python scripts/mcp_server.py`). Zgodne z Claude Code, Cursor, Gemini CLI i dowolnym nowoczesnym frameworkiem agentów.

```bash
# Add as stdio MCP server in your agent harness
python scripts/mcp_server.py
```

### 2. Natywna Instalacja w Hermes
Ze środowiska instalacji Hermes uruchom:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Zainstaluj pozostałe umiejętności, zastępując nazwę katalogu w pełnym identyfikatorze. Zwykły tap odczytuje domyślną gałąź. Powiązane umiejętności sprawdzone na commicie `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video.

## Dostęp do Źródeł Danych

- Podstawowe zapytania OpenAlex można uruchamiać anonimowo z mniejszym budżetem dziennym ($0.10/dzień anonimowo i $1/dzień z darmowym kluczem API, limit 100 żądań/sekundę). Przechowuj opcjonalny klucz w `OPENALEX_API_KEY`.
- Crossref zapewnia publiczny dostęp do metadanych z ograniczaniem przepustowości. Sygnały aktualizacji i Retraction Watch wymagają kontroli DOI.
- Unpaywall wymaga rzeczywistego adresu e-mail w `UNPAYWALL_EMAIL`.
- arXiv, Europe PMC, PubMed i DOAJ są źródłami uzupełniającymi z własnymi zasadami. Scite, Dimensions, Scopus i Web of Science to opcjonalne usługi zewnętrzne.

## Walidacja

Użyj dedykowanego środowiska Python. Zależności QA obejmują wszystkie testy wykonywalne:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA weryfikuje metadane, odwołania, wzorce ścieżek osobistych i znanych sekretów, składnię Pythona oraz oznaczone bloki kodu. Zwraca 0 przy sukcesie, 1 przy błędzie kodu/schematu/tożsamości oraz 2 przy niedostępności transportu/uwierzytelniania/limitu.

CI uruchamia pełny zestaw testów w systemach Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview, Windows x86_64, Windows ARM64, macOS ARM64 i macOS Intel, z 713 zaliczonymi testami jednostkowymi i 40 zweryfikowanymi blokami kodu wykonywalnego.

tools/longtail/ zawiera deterministyczny generator skrajnych scenariuszy długiego ogona: 4096 kombinacji kandydatów z ziarnem SHA256 na rozdzielonych osiach czynników, zachłanny wybór pokrycia i raport w generated-scenarios.json.

scripts/scfabric/ to struktura obliczeń naukowych: sonda sprzętowa, katalog backendów z bramkami typów danych, pięć profili obciążenia i ComputeReceipt. Pomiary zarejestrowane w [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md).

## Dokumenty Badawcze i Planistyczne

Te dokumenty są eksploracyjnymi odniesieniami planistycznymi, a nie wiążącą mapą drogową.

- [Atlas Problemów v0 (Angielski)](../../docs/pain-atlas-v0.en.md), [Wersja Chińska](../../docs/pain-atlas-v0.zh.md): Punkty tarcia w cyklu akademickiej pracy wiedzy ze statusami weryfikacji.
- [Plan Badań v0 (Angielski)](../../docs/research-plan-v0.en.md), [Wersja Chińska](../../docs/research-plan-v0.zh.md): Model Research Object, kluczowe obszary kompetencji i macierz dekompozycji czynników.
