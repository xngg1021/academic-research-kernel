# academic-research-kernel (pt)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Núcleo neutro de pesquisa acadêmica e conjunto de deliberação multiagente. Fornece 13 habilidades acadêmicas e ferramentas de verificação com pontos de entrada portáteis Agent Plugins v1 e MCP (Model Context Protocol), além de integração nativa para Hermes Agent, Claude Code, Cursor e subagentes CLI personalizados.

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Licença: [Source Lineage License 1.0](../../LICENSE).

## Licença

Este instantâneo adota a **Source Lineage License 1.0** para o material coberto identificado em [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). Os instantâneos históricos até `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` mantêm a licença MIT original.

## Habilidades

| Habilidade | Versão | Descrição |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Verificação cruzada de identidade e contagem de citações; inspeção de atualizações e retratações; localização de texto OA e verificação de PDF |
| `skills/literature-analysis` | 1.3.0 | Doze fluxos de trabalho: similaridade de temas, sobreposição de texto, contra-evidências, perfis de autores, revisão simulada e verificação de falácias |
| `skills/academic-writing` | 1.1.1 | Redação e edição acadêmica, diretrizes de citação (ISO 690, APA, MLA, Chicago, IEEE, AMA e perfis regionais) e regras de periódicos |
| `skills/math-computation` | 1.2.1 | Roteamento de domínios matemáticos com receitas numéricas e estatísticas; arquivos de referência avançados |
| `skills/quantitative-paper-audit` | 1.1.0 | Recálculo de estatísticas relatadas (tamanho de efeito, valores p, intervalos de confiança, OR/RR) e detecção de discrepâncias |
| `skills/research-reproducibility` | 1.0.1 | Pipeline de auditoria de reprodutibilidade em 14 etapas com listas de verificação estruturadas e registros reproduzíveis |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Registros de busca PRISMA, triagem de literatura, conversão de tamanho de efeito, heterogeneidade e agrupamento |
| `skills/literature-watch` | 1.1.0 | Monitoramento semanal: acompanhamento de tópicos, autores e citações de DOI no OpenAlex e Crossref sem duplicatas |
| `skills/retraction-watch` | 1.1.0 | Monitoramento semanal: verificação de lista de DOIs contra registros de retratação e atualizações no OpenAlex e Crossref |
| `skills/research-object-identity` | 1.1.0 | Identificação determinística de recursos de pesquisa e rastreamento de proveniência com validação de DAG causal |
| `skills/claim-evidence-graph` | 1.0.0 | Conexão determinística entre asserções científicas, registros de evidências e proveniência computacional |
| `skills/decision-ledger` | 1.0.0 | Registro de Decisão de Pesquisa: log determinístico e somente de anexação de decisões, tentativas falhas e status de rotas |
| `skills/cross-review-five` | 2.0.0 | Orquestração dinâmica de painel multirevisor para modelos heterogêneos com atribuição de Kuhn-Munkres e deliberação esparsa v2 |

## Padrões Acadêmicos e Linha de Base Multi-Perfil

O repositório adota **ISO 690:2021** (Referências bibliográficas), **ISO 5127:2017** (Fundamentos e vocabulário) e **W3C PROV** (Modelo de proveniência) como linhas de base internacionais, ao lado de perfis regionais e normas disciplinares (APA 7th, IEEE, PRISMA 2020, ICMJE). Veja a [Arquitetura de Padrões](../../docs/standards/README.md) e o [Guia de Terminologia](../../docs/terminology/README.md).

## Integração e Uso Portátil

```bash
python scripts/mcp_server.py
```

## Validação e CI

A integração contínua (CI) executa o conjunto completo de testes no Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview-Canary, Windows x86_64, Windows ARM64, macOS ARM64 e macOS Intel, com 625 testes unitários aprovados e verificação de canary em tempo real.

## Documentos de Pesquisa e Planejamento

- [Atlas de Dores v0 (Inglês)](../../docs/pain-atlas-v0.en.md), [Versão em Chinês](../../docs/pain-atlas-v0.zh.md): Pontos de fricção no ciclo de trabalho acadêmico com verificação de fontes.
- [Plano de Pesquisa v0 (Inglês)](../../docs/research-plan-v0.en.md), [Versão em Chinês](../../docs/research-plan-v0.zh.md): Modelo Research Object, áreas de competência fundamentais e matriz de decomposição fatorial.
