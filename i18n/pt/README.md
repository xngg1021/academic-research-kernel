# academic-research-kernel (pt)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Núcleo neutro de pesquisa acadêmica e conjunto de deliberação multiagente. Fornece 13 habilidades acadêmicas e ferramentas de verificação com pontos de entrada portáteis Agent Plugins v1 e MCP (Model Context Protocol), além de integração nativa para Hermes Agent, Claude Code, Cursor e subagentes CLI personalizados. Abrange verificação de fontes, análise de literatura, redação acadêmica, computação numérica, auditoria quantitativa de artigos, auditorias de reprodutibilidade, revisão sistemática e meta-análise, identidade e linhagem de objetos de pesquisa, orquestração dinâmica de revisão cruzada entre modelos, além de duas automações semanais de monitoramento. O repositório inclui verificações executáveis de exemplo; o escopo de validação e as limitações de serviços externos estão registrados na [auditoria](../../docs/audit-20260906.md).

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Oferta delimitada atual: [Source Lineage License 1.0](../../LICENSE).

## Licença

O instantâneo que contém este aviso adota a **Source Lineage License 1.0** para o Material Coberto e os direitos identificados em [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). O primeiro commit e árvore SLL, e o posterior commit de registro de limite, são distinguidos em [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) e [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Instantâneos a partir dessa transição registrada que mantenham este aviso carregam a mesma oferta delimitada.

Instantâneos históricos até `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` foram licenciados sob MIT, sujeitos aos termos aplicáveis àquelas cópias. Os destinatários retêm permissões MIT válidas e não precisam migrar para a SLL. O [texto MIT anterior do projeto](../../LICENSES/MIT-pre-SLL.txt) é preservado; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) e sua proveniência de terceiros permanecem inalterados. A nova oferta raiz não revoga esses direitos.

A SLL permite amplamente o uso, estudo, modificação, uso comercial, distribuição e adições proprietárias, sujeitos às condições aplicáveis de licença, aviso e linhagem de fonte. Ela não é copyleft e não exige divulgação de código-fonte. O serviço de rede puro sem fornecimento de cópias não aciona, por si só, a condição de aviso de linhagem de serviço Core. Não há concessão expressa de patentes. O material de terceiros permanece sob seus próprios termos. O [LICENSE](../../LICENSE) exato em inglês rege este resumo informativo; `LicenseRef-Source-Lineage-1.0` é uma referência local, não uma atribuição SPDX, e nenhuma aprovação da OSI é reivindicada. O [recebimento de contribuições](../../CONTRIBUTING.md) é separado das permissões de licença a jusante.

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

Existem 21 arquivos de referência Markdown nas treze habilidades. As referências são carregadas apenas quando necessárias.

## Padrões Acadêmicos e Linha de Base Multi-Perfil

Estilos de citação, critérios de relatório e contratos de metadados dependem do periódico-alvo, instituição, financiador, disciplina e jurisdição. O repositório estabelece **ISO 690:2021** (Referências bibliográficas), **ISO 5127:2017** (Vocabulário de informação e documentação) e **W3C PROV** (Modelo de dados de proveniência) como linhas de base internacionais, ao lado de perfis regionais e normas disciplinares (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Os requisitos do local de publicação têm precedência sobre os perfis padrão. Veja a [Arquitetura de Padrões Acadêmicos](../../docs/standards/README.md) e o [Guia de Terminologia Natural](../../docs/terminology/README.md).

## Integração e Uso Portátil

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
Este repositório está em conformidade com a especificação neutra **Agent Plugins v1** (`../../plugin.json`) e expõe ferramentas essenciais de verificação acadêmica e recálculo estatístico por meio de um **servidor MCP** via stdio (`../../mcp.json` / `python scripts/mcp_server.py`). Compatível com Claude Code, Cursor, Gemini CLI e qualquer framework moderno de agentes.

```bash
# Add as stdio MCP server in your agent harness
python scripts/mcp_server.py
```

### 2. Instalação Nativa no Hermes
A partir de uma instalação do Hermes execute:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Instale as demais habilidades substituindo o nome do diretório no identificador completo. Um tap comum lê o branch padrão. Habilidades relacionadas empacotadas verificadas no commit `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video.

## Acesso a Fontes de Dados

- Consultas básicas ao OpenAlex podem ser executadas anonimamente com orçamento diário limitado ($0.10/dia anônimo e $1/dia com chave gratuita, teto de 100 req/s). Armazene chave opcional em `OPENALEX_API_KEY`.
- O Crossref fornece acesso público a metadados com controle de taxa. Sinais de atualização e do Retraction Watch exigem checagem de DOI e direção.
- O Unpaywall exige um e-mail de contato válido em `UNPAYWALL_EMAIL`.
- arXiv, Europe PMC, PubMed e DOAJ são fontes complementares com políticas próprias. Scite, Dimensions, Scopus e Web of Science são serviços externos opcionais.

## Validação

Use um ambiente Python dedicado. As dependências de QA cobrem todas as verificações executáveis:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

O QA valida metadados, referências, padrões de caminhos pessoais e segredos, sintaxe Python e blocos de código marcados. Retorna 0 para sucesso, 1 para falha de código/schema/identidade e 2 para indisponibilidade de transporte/autenticação/cota.

O CI executa a suíte completa de testes no Linux x86_64 (Python 3.10-3.14), Linux ARM64, Ubuntu 26.04 Preview, Windows x86_64, Windows ARM64, macOS ARM64 e macOS Intel, com 654 testes unitários aprovados e 40 blocos de código executáveis validados.

tools/longtail/ contém o gerador determinístico de cenários extremos de cauda longa: 4096 combinações candidatas com semente SHA256 sobre eixos desacoplados, seleção de cobertura e relatório em generated-scenarios.json.

scripts/scfabric/ é a estrutura de computação científica: sonda de hardware, catálogo de backends com filtros dtype, cinco perfis de carga e ComputeReceipt. Medições registradas em [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md).

## Documentos de Pesquisa e Planejamento

Estes documentos são referências exploratórias de planejamento, não um roteiro obrigatório.

- [Atlas de Dores v0 (Inglês)](../../docs/pain-atlas-v0.en.md), [Versão em Chinês](../../docs/pain-atlas-v0.zh.md): Pontos de fricção no ciclo de trabalho acadêmico com verificação de fontes.
- [Plano de Pesquisa v0 (Inglês)](../../docs/research-plan-v0.en.md), [Versão em Chinês](../../docs/research-plan-v0.zh.md): Modelo Research Object, áreas de competência fundamentais e matriz de decomposição fatorial.
