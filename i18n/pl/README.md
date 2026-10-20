# academic-research-kernel (pl)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Deterministyczny system zarządzania stanem badań naukowych i weryfikacji metodologicznej dla procesów badawczych wspomaganych przez agentów, niezależny od środowiska wykonawczego. Łączy identyfikację obiektów badawczych, rejestr dowodów / weryfikacji danych empirycznych, powiązania między twierdzeniami a dowodami (CEG) oraz dopisywalny rejestr decyzji badawczych i nieudanych prób poprzez mechanizm obejmujący pozyskiwanie i parsowanie artefaktów badawczych oraz uniwersalny serwer Model Context Protocol (MCP). Czternaście wyspecjalizowanych umiejętności akademickich wytwarza i przetwarza zweryfikowany stan badań przy natywnym wsparciu dla Claude Code, Cursor, Codex, Gemini CLI oraz Hermes Agent. Zakres walidacji i ograniczenia usług zewnętrznych udokumentowano w [raporcie z audytu](../../docs/kernel-architecture.md).

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Obowiązująca oferta licencyjna: [Source Lineage License 1.0](../../LICENSE).

## Szybki start

Uruchom wersję 2.2.0 za pomocą narzędzia [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx academic-research-kernel@2.2.0 mcp
```

Opis [wydania 2.2.0](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.2.0) zawiera sumy kontrolne pakietów dystrybucyjnych i status publikacji. Pakiet wheel wydania można również uruchomić lokalnie poleceniem `uvx --from ./academic_research_kernel-2.2.0-py3-none-any.whl academic-research-kernel mcp`. Obsługiwane są wersje Python 3.10–3.14; przełącznik `uvx --python 3.12` jawnie wybiera obsługiwany interpreter. Wszystkie 12 deterministycznych narzędzi, w tym moduły statystyczne, wchodzi w skład instalacji podstawowej.

## Weryfikacja instalacji

```bash
uvx academic-research-kernel@2.2.0 doctor
uvx academic-research-kernel@2.2.0 --version
```

Diagnostyka offline sprawdza zależności, schematy oraz definicje wszystkich 12 narzędzi. Opcjonalne usługi zewnętrzne mogą pozostać nieskonfigurowane. Użyj `doctor --json`, aby uzyskać wynik w formacie przeznaczonym do odczytu maszynowego.

## Instalacja pakietu

```bash
uv tool install academic-research-kernel==2.2.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Alternatywnie pakiet można zainstalować poleceniem `pipx install academic-research-kernel==2.2.0` lub `python -m pip install academic-research-kernel==2.2.0` wewnątrz obsługiwanego środowiska wirtualnego. Dodatek `[full]` instaluje biblioteki dla rozszerzonych przykładów obliczeniowych; `[qa]` dodaje narzędzia walidacyjne repozytorium wraz z parserem plików PDF. Dodatek `[research]` instaluje pakiety `pypdf==6.19.0` oraz `fonttools==4.65.0` w celu zapewnienia spójnego dekodowania czcionek PDF w czystych instalacjach (oba pakiety obsługują Python 3.10). Ustrukturyzowany odczyt HTML/XML oraz ograniczony rozmiarowo odczyt plików DOCX/XLSX korzystają ze standardowej biblioteki języka Python. Backendy GPU i płatne usługi zewnętrzne pozostają opcjonalne.

## Hermes

Zainstaluj `uv`, tak aby znajdował się w zmiennej `PATH` procesu Hermes, a następnie zainstaluj i jawnie włącz przenośną wtyczkę:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

Dotychczasowy identyfikator `academic-skills` został zachowany dla kompatybilności wstecznej i obejmuje 14 umiejętności, w tym `paper-research`. Plik `mcp.json` wtyczki wywołuje `uv run --frozen --no-dev --no-editable` z Pythonem 3.12 oraz plikiem `uv.lock` repozytorium, utrzymując odizolowane środowisko wykonawcze w `${PLUGIN_DATA}/runtime`. Przy pierwszym uruchomieniu zależności są instalowane automatycznie bez korzystania z pakietów Pythona należących do Hermesa lub systemu operacyjnego; pobranie brakujących pakietów lub interpretera wymaga połączenia z siecią. Starsza metoda instalacji samych umiejętności przez mechanizm tap pozostaje dostępna i została opisana poniżej w sekcji dotyczącej integracji.

## Uruchamianie ze źródeł

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Informacje o klasyfikacji zależności, odtwarzaniu pakietów, identyfikacji wydań, punktach kontrolnych publikacji i zakresie walidacji znajdują się w dokumencie [dystrybucja i wydania](../../docs/distribution-release.md).

## Licencja

Migawka zawierająca niniejszą informację przyjmuje licencję **Source Lineage License 1.0** w odniesieniu do Materiału Objętego Licencją oraz praw wskazanych w dokumencie [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Pierwszy commit i drzewo SLL oraz późniejszy commit rejestrujący granicę przejścia zostały rozróżnione w plikach [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) oraz [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Kolejne migawki po tym zarejestrowanym przejściu, które zachowują niniejszą informację, są udostępniane na tych samych warunkach.

Historyczne migawki aż do `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` były udostępniane na licencji MIT, zgodnie z warunkami właściwymi dla tamtych kopii. Odbiorcy zachowują ważne uprawnienia wynikające z licencji MIT i nie mają obowiązku przechodzenia na SLL. [Poprzedni tekst licencji MIT projektu](../../LICENSES/MIT-pre-SLL.txt) został zachowany; plik [tests/upstream/LICENSE](../../tests/upstream/LICENSE) oraz pochodzenie komponentów stron trzecich pozostają bez zmian. Nowa oferta licencyjna w katalogu głównym nie uchyla tamtych wcześniejszych praw.

Licencja SLL szeroko zezwala na używanie, badanie, modyfikowanie, wykorzystanie komercyjne, dystrybucję oraz tworzenie własnościowych rozszerzeń, z zastrzeżeniem odpowiednich warunków licencyjnych, informacyjnych i dotyczących rodowodu kodu źródłowego. Nie jest to licencja typu copyleft i nie wymaga ona ujawniania kodu źródłowego. Świadczenie czystej usługi sieciowej bez przekazywania kopii nie uruchamia samo przez się warunku informowania o pochodzeniu usługi głównej (Core). Licencja nie udziela wyraźnych praw patentowych, a materiały stron trzecich podlegają własnym postanowieniom. Wiążący dla niniejszego podsumowania jest oryginalny angielski tekst [LICENSE](../../LICENSE); oznaczenie `LicenseRef-Source-Lineage-1.0` stanowi odniesienie lokalne, a nie identyfikator nadany przez SPDX, i nie deklaruje się zatwierdzenia przez OSI. Zasady [przyjmowania wkładów](../../CONTRIBUTING.md) są odrębne od uprawnień licencyjnych użytkowników końcowych.

## Umiejętności

| Umiejętność | Wersja | Zastosowanie |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Krzyżowa weryfikacja tożsamości publikacji i liczby cytowań w poszczególnych bazach; sprawdzanie sygnałów aktualizacji i wycofania artykułów (retrakcji); lokalizowanie pełnych tekstów Open Access oraz weryfikacja plików PDF |
| `skills/literature-analysis` | 1.3.0 | Dwanaście procedur badawczych: podobieństwo tematyczne, lokalne pokrywanie się tekstu, kontrargumenty, profile autorów, symulowana recenzja, wykrywanie błędów logicznych, macierz przeglądu, dobór czasopism, BibTeX, czytanie dwujęzyczne, identyfikacja luk badawczych i odtwarzanie wyników |
| `skills/academic-writing` | 1.1.1 | Redakcja tekstów naukowych, wytyczne dotyczące cytowania (ISO 690, APA, MLA, Chicago, IEEE, AMA i profile regionalne), instrukcje redakcyjne czasopism, opcjonalne usługi detekcji, materiały zgłoszeniowe oraz wymogi instytucjonalne |
| `skills/math-computation` | 1.2.1 | Kierowanie zadań według dziedziny i typu obliczeń ze zweryfikowanymi przykładami numerycznymi i statystycznymi; cztery specjalistyczne pliki referencyjne |
| `skills/quantitative-paper-audit` | 1.1.0 | Ponowne przeliczanie deklarowanych statystyk (wielkość efektu, wartości p, przedziały ufności, OR/RR, osiągnięta moc testu) oraz wykrywanie rozbieżności liczbowych |
| `skills/research-reproducibility` | 1.0.1 | Czternastoetapowy potok audytu powtarzalności z ustrukturyzowanymi listami kontrolnymi, pięcioma poziomami weryfikacji faktów i powtarzalnymi rekordami audytowymi |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Dzienniki wyszukiwania PRISMA, rejestr selekcji literatury, konwersja wielkości efektu, ocena heterogeniczności, łączenie wyników w modelach efektów stałych i losowych, analiza wrażliwości oraz diagnostyka błędu publikacyjnego |
| `skills/literature-watch` | 1.1.0 | Cotygodniowy monitoring: śledzenie tematów, autorów i prac cytujących wskazane DOI w bazach OpenAlex i Crossref wraz z deduplikacją i raportowaniem wyłącznie nowych pozycji |
| `skills/retraction-watch` | 1.1.0 | Cotygodniowy monitoring: weryfikacja listy obserwowanych DOI względem flagi `is_retracted` w OpenAlex oraz rekordów aktualizacji w Crossref (sygnały `update-to`); raportowanie wyłącznie zmian statusu |
| `skills/research-object-identity` | 1.1.0 | Deterministyczna identyfikacja zasobów naukowych oraz proweniencja / identyfikowalność: normalizacja identyfikatorów, pięciostanowa weryfikacja, grafy derywacji adresowane treścią, walidacja przyczynowych grafów DAG i śledzenie pochodzenia poniżej 100 ms |
| `skills/claim-evidence-graph` | 1.0.0 | Deterministyczne powiązania między twierdzeniami a dowodami łączące hipotezy naukowe, rejestry dowodów i proweniencję obliczeniową |
| `skills/decision-ledger` | 1.0.0 | Rejestr decyzji badawczych i nieudanych prób: deterministyczny rejestr tylko do dopisywania obejmujący wybory metodologiczne, wyniki negatywne, status ścieżki badawczej / powód porzucenia ścieżki oraz rewizje wniosków |
| `skills/paper-research` | 1.0.0 | Odczyt artykułów i materiałów dodatkowych na podstawie DOI, adresu URL lub plików lokalnych wraz z walidacją wyodrębnionych pól, kontrolą statystyczną, trwałym zapisem stanu badań, raportami w języku chińskim powiązanymi ze źródłami oraz porównaniem dwóch prac |
| `skills/cross-review-five` | 2.0.0 | Dynamiczna orkiestracja wieloosobowego panelu recenzentów obsługująca dowolne modele i podagentów (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini i in.): potok Sparse Deliberation v2 z algorytmem węgierskim Kuhna-Munkresa, grupowaniem twierdzeń, ukierunkowaną anonimową polemiką i oceną istotności P0–P3 |

Czternaście umiejętności obejmuje łącznie 22 pliki referencyjne Markdown, które są wczytywane wyłącznie w razie potrzeby.

## Standardy Akademickie i Wieloprofilowa Linia Bazowa

Style cytowań, kryteria raportowania wyników oraz schematy metadanych zależą od docelowego czasopisma, instytucji naukowej, agencji finansującej, dyscypliny i jurysdykcji. Jako międzynarodową linię bazową repozytorium przyjmuje normy **ISO 690:2021** (Przypisy bibliograficzne), **ISO 5127:2017** (Słownictwo informacji i dokumentacji) oraz **W3C PROV** (Model danych proweniencji), uzupełnione o profile regionalne (np. GB/T 7714-2025 w Chinach kontynentalnych, UNE-ISO 690:2024 w Hiszpanii, DIN ISO 690:2021 w Niemczech) oraz standardy dyscyplinarne (APA wyd. 7, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Wymogi docelowego miejsca publikacji mają pierwszeństwo przed profilami domyślnymi. Szczegóły opisano w dokumentach [Architektura Standardów Akademickich](../../docs/standards/README.md) oraz [Przewodnik po Naturalnej Terminologii](../../docs/terminology/README.md).

Końcowa naprawa integralności potwierdza spójność identyfikatorów DOI i identyfikatorów zewnętrznych, wzajemne wykluczanie się flag logicznych w werdyktach ilościowych oraz wspólny kontrakt dla struktury „punkty wymagające weryfikacji” pomiędzy jądrem a potwierdzeniami pobrania. Kompletność pamięci podręcznej jest odtwarzana na podstawie zachowanych kopert źródłowych i znormalizowanych powiązań niezależnie od list mutacji w potwierdzeniu; jednoczesne usunięcie rekordu oraz jego deklaracji w pamięci podręcznej nie pozwala na uzyskanie zaakceptowanego odtworzenia. Zobacz [podsumowanie zamknięcia czterech blokad](../../docs/kernel-architecture.md).

## Integracja i Przenośne Użycie

### 1. Universal Agent Plugins v1 oraz Model Context Protocol (MCP)
Repozytorium spełnia niezależną od dostawcy specyfikację **Agent Plugins v1** (`../../plugin.json`) i udostępnia podstawowe narzędzia weryfikacji bibliograficznej oraz ponownego przeliczania statystyk przez **serwer MCP** komunikujący się przez stdio (`../../mcp.json` / `../../scripts/mcp_server.py`). Rozwiązanie współpracuje z Claude Code, Cursor, Gemini CLI i każdym nowoczesnym środowiskiem agentowym. Chociaż główny identyfikator repozytorium to `academic-research-kernel`, nazwa manifestu wtyczki `academic-skills` oraz aliasy konfiguracji MCP pozostają niezmienione ze względu na kompatybilność wsteczną.

```bash
# Add as stdio MCP server in your agent harness
uvx academic-research-kernel mcp
```

### 2. Natywna Instalacja w Hermes
W zainstalowanym środowisku Hermes wykonaj:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Pozostałe umiejętności instaluje się poprzez podmianę nazwy katalogu w pełnym identyfikatorze. Standardowe polecenie tap odczytuje domyślną gałąź repozytorium i instaluje powyższy zestaw umiejętności. Aby przetestować gałąź roboczą przed jej scaleniem, pobierz tę gałąź lokalnie i postępuj zgodnie z instrukcją instalacji z katalogu lokalnego właściwą dla zainstalowanej wersji programu Hermes; nie należy zakładać, że polecenie tap wybiera gałąź przeglądu zmian.

Powiązane umiejętności zweryfikowane względem migawki upstream `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf oraz manim-video. Pakiety huggingface-hub i llama-cpp znajdują się w katalogu opcjonalnym i mogą wymagać osobnej instalacji. Pozycje ocr-and-documents oraz pc-hardware-benchmark nie występowały w tej migawce i nie stanowią zależności. Narzędzia sesyjne oraz obsługa dokumentów i przeglądarki zależą od konfiguracji lokalnej.

## Dostęp do Źródeł Danych

- Podstawowe zapytania do bazy OpenAlex mogą być wykonywane anonimowo w ramach mniejszego budżetu dziennego. Według dokumentacji zweryfikowanej w dniu 2026-09-06 limit wynosi 0,10 USD/dzień w trybie anonimowym oraz 1 USD/dzień z bezpłatnym kluczem API, przy pułapie 100 żądań na sekundę. Koszty zależą od rodzaju zapytania i nie oznaczają nielimitowanego dostępu. Opcjonalny klucz należy zapisać w zmiennej `OPENALEX_API_KEY` oraz korzystać z parametru `per_page` (maksymalnie 100) i stronicowania kursorowego.
- Crossref zapewnia publiczny dostęp do metadanych z ograniczeniem częstotliwości zapytań. Relacje aktualizacji oraz sygnały Retraction Watch wymagają sprawdzania numeru DOI i kierunku powiązania; brak wpisów nie dowodzi, że dana praca jest wolna od korekt lub wycofania.
- Unpaywall wymaga podania prawdziwego adresu e-mail do kontaktu w zmiennej `UNPAYWALL_EMAIL`. Brak zwróconej lokalizacji nie oznacza, że kopia w otwartym dostępie nie istnieje.
- arXiv, Europe PMC, PubMed E-utilities oraz DOAJ to źródła uzupełniające objęte własnymi regulaminami i nie wszystkie są wywoływane podczas standardowych testów. Semantic Scholar stosuje współdzielone limity dla zapytań anonimowych oraz odrębne przydziały dla kluczy API; sam dostęp do usługi nie gwarantuje dostępności kontekstu cytowań.
- Scite, Dimensions, Scopus, Web of Science oraz narzędzia do wykrywania tekstów generowanych przez AI są opcjonalnymi usługami zewnętrznymi. Przed ich użyciem należy sprawdzić bieżące uprawnienia konta, dostęp do API i limity zapytań; nie gwarantuje się powszechnego planu bezpłatnego ani stałych cen.

Zobacz dokumentację dotyczącą [uwierzytelniania w OpenAlex](https://help.openalex.org/api/authentication/), [budżetów i kosztów zapytań](https://help.openalex.org/api/llm-quick-reference/) oraz [filtrów aktualizacji Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Deterministyczne pozyskiwanie danych i publiczne jądro

Warstwa odpowiedzialna za pozyskiwanie i parsowanie artefaktów badawczych udostępnia struktury `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 adapterów (odpowiadających 14 umiejętnościom oraz rezerwowemu adapterowi nieprzezroczystemu `opaque fallback`) i 12 bezstanowych narzędzi stdio MCP. Zaakceptowane potwierdzenia pobrania wiążą każdą zachowaną zmianę semantyczną według rodzaju, tożsamości i kanonicznego skrótu SHA-256: obiekty badawcze, rekordy powiązań twierdzeń z dowodami (CEG), wpisy rejestru decyzji, punkty wymagające weryfikacji, potwierdzenia fizyczne oraz rejestracje artefaktów. Odtwarzanie z pamięci podręcznej weryfikuje te zobowiązania niezależnie od skrótów migawek transportowych. Puste rejestry są poprawne, a nieudane wsady atomowe nie pozostawiają stanu częściowego.

Uprawnienia do odczytu treści pochodzenia są jawne i przekazywane poza pasmem podstawowym. Zaufane wywołania w języku Python przekazują obiekt `LineageVerificationContext` podczas odtwarzania zserializowanych potwierdzeń lub migawek; wywołania przez MCP mogą dostarczyć ograniczoną liczbę bajtów treści, lecz nigdy nie przekazują katalogu głównego systemu plików hosta. Domyślny limit treści wynosi 10 MiB, przy czym zaufany host może jawnie autoryzować większe artefakty w ramach wspólnej polityki między wytwórcą a weryfikatorem. Bez potwierdzonego dostępu do treści status `fully_verified` nie może zostać niezależnie odtworzony i zwraca ustrukturyzowany wynik informujący o nieprawidłowej weryfikacji. Tekst nieustrukturyzowany pozostaje nieprzezroczysty, zdania odrębne pozostają widoczne, a badacze zachowują pełną kontrolę nad zatwierdzaniem zmian, zamykaniem lub wznawianiem ścieżek badawczych, kierowaniem zadań oraz oceną merytoryczną.

Szczegółowe kontrakty i reguły kompatybilności opisano w [architekturze jądra](../../docs/kernel-architecture.md). Punkty kontrolne dystrybucji i publikacji zestawiono w [przewodniku po wydaniach](../../docs/distribution-release.md). Pliki README w języku angielskim i chińskim uproszczonym są aktualizowane na bieżąco, natomiast status pozostałych tłumaczeń jest jawnie ewidencjonowany w [manifeście synchronizacji](../../docs/i18n/manifest.json). Tożsamość kandydata wydania, wyniki CI dla dokładnego commita oraz zbiorcza dokumentacja przeglądów znajdują się w [rejestrze zamknięcia](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Walidacja

Należy korzystać z dedykowanego środowiska Python. Biblioteki wykonawcze zależą od konkretnego zadania i nie muszą być domyślnie zainstalowane w programie Hermes. Zależności QA są szersze, aby umożliwić uruchomienie wszystkich oznaczonych przykładów:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

Procedura QA weryfikuje metadane, odwołania lokalne, wzorce ścieżek prywatnych i znanych sekretów, składnię języka Python oraz oznaczone wykonywalne bloki kodu. Każdy przykład `smoke` uruchamiany jest bez modyfikacji w nowym podprocesie. Przykłady generujące wykresy obsługują zmienną `PLOT_DIR` (domyślnie `~/plots`, rozwijaną jawnie), a podczas testów korzystają z katalogu tymczasowego. Niesklasyfikowane bloki kodu Python są odrzucane; bloki `fragment:` przechodzą kontrolę składni, lecz wymagają nazwanych danych wejściowych i nie są uruchamiane samodzielnie. Bloki `external-test:` są uruchamiane wyłącznie przez ręczne polecenie weryfikacji zewnętrznej, które zwraca `0` po pomyślnym przejściu skonfigurowanych testów, `1` w przypadku błędu kodu, schematu lub tożsamości oraz `2` w razie niedostępności sieci, uwierzytelniania lub limitu zapytań, pozostawiając nieskonfigurowane usługi opcjonalne ze statusem `SKIP`.

Przypięte testy tworzenia umiejętności programu Hermes są wykorzystywane ponownie bez zmiany reguł przypisanych do poszczególnych umiejętności. Globalne kontrole całej dystrybucji nadrzędnej nie mają zastosowania do tego repozytorium; nasz zestaw testowy sprawdza czternaście umiejętności i rozwiązuje odwołania względem przypiętego katalogu pakietów wbudowanych i opcjonalnych. Nie stanowi to pełnego testu instalacji programu Hermes. Środowisko CI korzysta z sieci wyłącznie w celu instalacji zależności, a standardowe testy zmian nie wywołują zewnętrznych API naukowych.

CI uruchamia pełny pakiet QA na platformach Linux x86_64 (Python 3.10–3.14), Linux ARM64 (`ubuntu-24.04-arm`), Ubuntu 26.04 preview canary (`ubuntu-26.04` oraz `ubuntu-26.04-arm`), Windows x86_64, Windows ARM64 (`windows-11-arm`), macOS ARM64 (`macos-latest`) oraz macOS Intel (`macos-15-intel`), z bieżącą walidacją canary względem repozytorium nadrzędnego. Historyczny kandydat bazowy przeszedł pomyślnie 1165 testy lokalne. Aktualne wyniki napraw i granice pokrycia testowego zapisano w [raporcie z naprawy poprawności](../../docs/maintenance/correctness-repair-20261008.md), a dowody z uruchomień zdalnych wskazują osobno testowany commit `HEAD`. Osobny przepływ integracji tap uruchamia się przy zmianach w gałęzi `main`: instaluje przypiętą wersję programu Hermes wskazaną w `tests/upstream/provenance.json` i wykonuje polecenia `tap add`, `search`, `install` oraz `list` względem niniejszego repozytorium. Dokładne wersje, zakres kontroli i ograniczenia opisano w [raporcie z audytu](../../docs/kernel-architecture.md).

Katalog [tools/longtail/](../../tools/longtail/README.md) zawiera deterministyczny generator czynników długiego ogona: 4096 kandydatów inicjowanych ziarnem SHA-256, 30 wybranych scenariuszy oraz obliczany maszynowo raport pokrycia weryfikacji. Model v3 zlicza oddzielnie rodziny zdolności (E01), 14 rzeczywistych umiejętności repozytorium (E02) oraz cele zadań (E03). Każdy scenariusz ma przypisaną jedną umiejętność główną, obsługiwany cel zadania i kompatybilne zdolności; każda umiejętność musi wystąpić co najmniej dwa razy w ramach dwóch różnych celów, w tym swojego zadeklarowanego celu podstawowego. Rozbieżność względem katalogów umiejętności powoduje błąd walidacji. Rozwinięcie semantyczne (łańcuchy zadań, wyrocznie testowe i wstrzykiwanie wykonywanych zdarzeń) pozostaje odrębnym etapem; pokrycie czynnikowe nie dowodzi pokrycia wykonania całych przepływów pracy.

Moduł `scripts/scfabric/` stanowi pakiet narzędzi do obliczeń naukowych i statystyki: sondę sprzętową, katalog backendów z bramkami typów danych (`dtype`), pięć profili obciążenia, sparowany benchmark z kontrolą zgodności numerycznej oraz potwierdzenie `ComputeReceipt`. Pomiary z pierwszej rundy zapisano w dokumencie [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md); podstawowa zasada zakłada domyślne użycie procesora CPU oraz włączanie akceleratorów wyłącznie na podstawie ważnego potwierdzenia.

## Badanie artykułu naukowego za pomocą lokalnego Agenta

Zainstaluj pakiet `academic-research-kernel[research]==2.2.0` i wyeksportuj wbudowany przepływ pracy:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Pozwól, aby Work lub inny kompatybilny lokalny Agent odczytał wyeksportowany plik `SKILL.md`, a następnie wydaj polecenie:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Wystarczy podać identyfikator DOI, publiczny link lub ścieżkę do lokalnego pakietu plików. W przypadku dwóch publikacji poproś Agenta o porównanie danych, metod, warunków ewaluacji i wyników ze wskazaniem, które rezultaty są bezpośrednio porównywalne. W ramach jednego zadania Agent przeprowadzi odczyt tekstu oryginalnego, walidację wyodrębnionych pól kandydujących, ponowne obliczenia statystyczne, zapis w jądrze, wygenerowanie raportu oraz niezależną kontrolę źródeł. Istniejący interfejs MCP zachowuje swoje 12 narzędzi, natomiast nowa orkiestracja działa poprzez interfejs CLI oraz przenośną umiejętność.

Poszczególne etapy programu wywołuje się poleceniami:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

Polecenie `prepare` pobiera i parsuje materiały wejściowe do postaci manifestu, skrótów plików źródłowych oraz zlokalizowanych segmentów tekstu. Polecenie `finish` weryfikuje przygotowaną przez Agenta ustrukturyzowaną ekstrakcję i ponownie przelicza kwalifikujące się testy t/wartości p, wielkości efektu dla dwóch grup oraz liczebności i odsetki przy użyciu dostępnych narzędzi statystycznych, a następnie zapisuje stan jądra oraz raporty w języku chińskim w formatach Markdown i HTML. Polecenie `compare` waliduje jawną ocenę porównywalności warunków badawczych sporządzoną przez Agenta. Polecenia te nie zawierają wbudowanego rezydentnego modelu językowego: odczyt semantyczny wykonuje bieżący Agent zgodnie ze specyfikacją [paper-research](../../skills/paper-research/SKILL.md). Zapisane pliki oryginalne i migawki ekstrakcji umożliwiają deterministyczne odtwarzanie w trybie offline, podczas gdy pobieranie z sieci i ponowny odczyt semantyczny są rejestrowane jako odrębne operacje.

## Poprawki w wersji 2.0.1 i weryfikacja dystrybucji

Wydanie 2.0.1 obejmuje poprawki dokładności obliczeń statystycznych oraz obsługi protokołu. Publiczne narzędzie `academic_recompute_statistics` udostępnia wartości p testu t oraz wskaźniki `d` Cohena / `g` Hedgesa dla dwóch grup, natomiast przedziały ufności i ilorazy szans lub ryzyka (`OR/RR`) pozostają funkcjami niższego poziomu w języku Python. Gdy istotna jest dokładność zapisu w publikacji, należy przekazać parametr `p_value_literal` (na przykład `"1.0e-5"`) lub `p_value_decimals`. Literały tekstowe zachowują końcowe zera, natomiast wartości liczbowe przechowują wyłącznie swoją reprezentację numeryczną; sprzeczne źródła precyzji powodują jawny błąd. Porównania z zaokrąglaniem (`round-half-up`) obejmują dolną granicę przedziału i wykluczają granicę górną. Zwykła rozbieżność statystyczna stanowi poprawny wynik naukowy, natomiast błędne dane wejściowe lub częściowo nieudane obliczenia ustawiają flagę `isError`.

Kontrole wycofania publikacji (retrakcji) zapisują bieżącą obserwację (`True`/`False`/`unknown`) oddzielnie od ostatniej potwierdzonej wartości. Krótka rezerwacja przed zapytaniem porządkuje obserwacje dotyczące tego samego numeru DOI i zachowuje aktualizacje dla innych DOI. Bieżące obserwacje i potwierdzenia historyczne mają osobne wersje: późniejsze potwierdzenie może uzupełnić zachowaną historię, podczas gdy nowszy status `unknown` pozostaje jawnie oznaczony jako niezweryfikowany dla bieżącego sprawdzenia. Odpowiedzi HTTP używane w łańcuchach testów regresyjnych są oznaczone jako dane testowe.

Serwer MCP odpowiada na komunikaty `ping`, zachowuje ciszę wobec prawidłowych powiadomień (w tym `notifications/cancelled`) i utrzymuje aktywną sesję stdio po otrzymaniu nieprawidłowych danych wejściowych. Implementacja synchroniczna nie deklaruje wywłaszczającego anulowania zadań. Obsługa komunikatów jest zgodna z [kontraktem komunikatów MCP](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) oraz [specyfikacją ping](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Zbuduj i zweryfikuj pakiety dystrybucyjne bieżącej kopii roboczej w odizolowanym środowisku:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

Opcja `--source-checks` rozpakowuje kandydujący archiwum `sdist` bez modyfikacji poza drzewem repozytorium, ustawia zmienne `ARK_REPO` i `ARK_SDIST` na ten pakiet, a następnie uruchamia jego testy, statyczne kontrole QA, wykonywalne bloki kodu oraz weryfikację synchronizacji i18n. Instalacje z pakietów `wheel` oraz `sdist` korzystają z osobnych, czystych środowisk, natomiast `uvx` używa lokalnego pliku `wheel` z niezależną pamięcią podręczną. Raport końcowy rejestruje skróty artefaktów oraz rzeczywiste ścieżki importu. Cykliczne lekkie kontrole kompatybilności z programem Hermes (`pinned` oraz `latest`) raportują osobno testowany skrót SHA. Zewnętrzne pliki JSON kontraktów i podsumowania zadań używają statusów `healthy`, `degraded` oraz `failed`, jawnie oznaczając pominięte sondy.
