# academic-research-kernel (pl)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Neutralne jądro do badań akademickich i pakiet wieloagentowych narad. Zapewnia 13 umiejętności naukowych i narzędzi weryfikacyjnych z przenośnymi punktami wejścia Agent Plugins v1 i MCP (Model Context Protocol), a także natywną integrację dla Hermes Agent, Claude Code, Cursor i subagentów CLI.

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Licencja: [Source Lineage License 1.0](../../LICENSE).

## Licencja

Repozytorium przyjmuje **Source Lineage License 1.0** dla materiałów objętych licencją wskazanych w [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Historyczne migawki do `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` zachowują uprawnienia licencji MIT.

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

## Standardy Naukowe i Profile Wielojęzyczne

Repozytorium ustanawia **ISO 690:2021** (Przypisy bibliograficzne), **ISO 5127:2017** (Słownictwo i pojęcia) oraz **W3C PROV** (Model proweniencji) jako międzynarodowe linie bazowe, obok profili regionalnych i standardów dziedzinowych (APA 7th, IEEE, PRISMA 2020, ICMJE). Zobacz [Architekturę Standardów](../../docs/standards/README.md) oraz [Przewodnik Terminologiczny](../../docs/terminology/README.md).

## Integracja i przenośne użycie

```bash
python scripts/mcp_server.py
```

## Walidacja i CI

CI uruchamia pełny pakiet QA w systemach Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 i macOS Intel, z 625 zaliczonymi testami jednostkowymi i ciągłą weryfikacją kanarkową upstream.

## Dokumenty Badawcze i Planistyczne

- [Atlas Problemów v0 (angielski)](../../docs/pain-atlas-v0.en.md), [Wersja chińska](../../docs/pain-atlas-v0.zh.md): Punkty tarcia w cyklu pracy naukowej z weryfikacją źródeł.
- [Plan Badawczy v0 (angielski)](../../docs/research-plan-v0.en.md), [Wersja chińska](../../docs/research-plan-v0.zh.md): Model Research Object, kluczowe obszary kompetencji i macierz dekompozycji czynnikowej.
