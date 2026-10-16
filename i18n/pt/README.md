# academic-research-kernel (pt)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

Ambiente determinístico de gestão de estado científico e verificação metodológica para fluxos de pesquisa assistidos por agentes, independente da plataforma de execução. O sistema unifica a identidade de objetos de pesquisa, o registro de evidência / verificação empírica, as relações entre alegações e evidências (CEG) e o registro de decisões de pesquisa e tentativas falhas em modo de anexação contínua, por meio da ingestão de artefatos de pesquisa e de um servidor universal Model Context Protocol (MCP). Quatorze habilidades acadêmicas especializadas produzem e consomem esse estado científico verificado, com suporte nativo para Claude Code, Cursor, Codex, Gemini CLI e Hermes Agent. O escopo de validação e as limitações de serviços externos estão documentados na [auditoria do projeto](../../docs/project-lineage-audit-20260920.md).

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Oferta de licença atual: [Source Lineage License 1.0](../../LICENSE).

## Início rápido

Execute a versão 2.1.0 com o [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx academic-research-kernel@2.1.0 mcp
```

O [lançamento 2.1.0](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0) registra os hashes de distribuição e o status de publicação. O pacote wheel distribuído também pode ser executado localmente com `uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`. Há suporte para Python 3.10–3.14, e `uvx --python 3.12` seleciona explicitamente um interpretador compatível. Todas as 12 ferramentas determinísticas, incluindo os módulos estatísticos, fazem parte da instalação básica.

## Verificar instalação

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

O diagnóstico offline verifica dependências, esquemas e as definições das 12 ferramentas. Serviços externos opcionais podem permanecer não configurados sem impedir o uso. Utilize `doctor --json` para obter saída estruturada legível por máquina.

## Instalação do pacote

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Como alternativa, instale com `pipx install academic-research-kernel==2.1.0` ou `python -m pip install academic-research-kernel==2.1.0` dentro de um ambiente virtual compatível. O extra `[full]` adiciona bibliotecas para exemplos científicos estendidos; `[qa]` instala as ferramentas de validação do repositório, incluindo o analisador de PDF. O extra `[research]` adiciona `pypdf==6.19.0` e `fonttools==4.65.0` para decodificação consistente de fontes em arquivos PDF em instalações limpas, ambos compatíveis com Python 3.10. A leitura estruturada de HTML/XML e de arquivos DOCX/XLSX delimitados utiliza apenas a biblioteca padrão. Backends de GPU e serviços pagos permanecem opcionais.

## Hermes

Instale o uv de modo que esteja disponível no `PATH` do processo do Hermes e, em seguida, instale e ative explicitamente o plugin portátil:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

A identidade `academic-skills` é preservada por compatibilidade e inclui as 14 habilidades acadêmicas, entre elas `paper-research`. O arquivo `mcp.json` do plugin executa `uv run --frozen --no-dev --no-editable` com Python 3.12 e o `uv.lock` do repositório, mantendo seu ambiente isolado em `${PLUGIN_DATA}/runtime`. Na primeira execução, o ambiente instala suas próprias dependências sem reutilizar pacotes Python do sistema ou do Hermes, exigindo acesso à rede caso faltem pacotes ou o interpretador. O método anterior de instalação apenas das habilidades via tap continua disponível na seção de integração portátil abaixo.

## A partir do código-fonte

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Consulte [distribuição e lançamento](../../docs/distribution-release.md) para detalhes sobre classificação de dependências, reprodução de pacotes, identidade de versão, pontos de verificação de publicação e escopo de validação.

## Licença

O instantâneo que contém este aviso adota a **Source Lineage License 1.0** para o Material Coberto e os direitos identificados em [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). O primeiro commit e árvore sob SLL, bem como o commit subsequente de registro de fronteira, são distinguidos em [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) e [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md). Os instantâneos posteriores a essa transição registrada que mantenham este aviso preservam a mesma oferta delimitada.

Os instantâneos históricos até `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` foram distribuídos sob licença MIT, sujeitos aos termos aplicáveis àquelas cópias. Os destinatários mantêm permissões MIT válidas e não precisam migrar para a SLL. O [texto MIT anterior do projeto](../../LICENSES/MIT-pre-SLL.txt) permanece preservado; [tests/upstream/LICENSE](../../tests/upstream/LICENSE) e sua proveniência de terceiros permanecem inalterados. A nova oferta na raiz não revoga esses direitos prévios.

A SLL permite amplamente o uso, estudo, modificação, uso comercial, distribuição e extensões proprietárias, sujeitos às condições aplicáveis de licença, aviso e linhagem de código-fonte. Ela não é copyleft e não exige revelação de código-fonte. A prestação pura de serviço em rede sem fornecimento de cópias não aciona, por si só, a condição de aviso de linhagem de serviço Core. Não há concessão expressa de patentes, e materiais de terceiros permanecem regidos por seus próprios termos. O texto original em inglês em [LICENSE](../../LICENSE) prevalece sobre este resumo informativo; `LicenseRef-Source-Lineage-1.0` é uma referência local, não um identificador SPDX, e não se reivindica aprovação da OSI. O [recebimento de contribuições](../../CONTRIBUTING.md) é independente das permissões de licença concedidas aos usuários.

## Habilidades

| Habilidade | Versão | O que faz |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Verificação cruzada de identidade e contagens de citações específicas por fonte; inspeção de sinais de atualização e retratação; localização de textos em acesso aberto e verificação de identidade de PDF |
| `skills/literature-analysis` | 1.3.0 | Doze fluxos de análise: similaridade temática, sobreposição textual local, contra-evidências, perfis de autores, revisão simulada, checagem de falácias, matriz de revisão, periódicos candidatos, BibTeX, leitura bilíngue, triagem de lacunas e reprodução |
| `skills/academic-writing` | 1.1.1 | Edição acadêmica, diretrizes de citação (ISO 690, APA, MLA, Chicago, IEEE, AMA e perfis regionais), instruções de periódicos, serviços opcionais de detecção, materiais de submissão e requisitos institucionais |
| `skills/math-computation` | 1.2.1 | Roteamento por domínio e tarefa matemática com exemplos numéricos e estatísticos revisados; quatro arquivos de referência especializada |
| `skills/quantitative-paper-audit` | 1.1.0 | Recálculo de estatísticas relatadas (tamanho de efeito, valores p, intervalos de confiança, OR/RR, poder estatístico obtido) e detecção de inconsistências numéricas |
| `skills/research-reproducibility` | 1.0.1 | Auditoria de reprodutibilidade em quatorze etapas com listas de verificação estruturadas, cinco níveis de evidência factual e registros de auditoria reproduzíveis |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Registros de busca PRISMA, registro de triagem de literatura, conversão de tamanho de efeito, heterogeneidade, agrupamento por efeitos fixos ou aleatórios, análise de sensibilidade e viés de publicação |
| `skills/literature-watch` | 1.1.0 | Monitoramento semanal: acompanhamento de temas, autores e obras que citam DOIs no OpenAlex e Crossref, com desduplicação e relato exclusivo de novos itens |
| `skills/retraction-watch` | 1.1.0 | Monitoramento semanal: nova verificação de listas de DOIs contra `is_retracted` no OpenAlex e registros de atualização no Crossref (sinais `update-to`), relatando apenas mudanças de status |
| `skills/research-object-identity` | 1.1.0 | Identificação determinística de recursos científicos e proveniência / rastreabilidade de artefatos: normalização de identificadores, verificação em cinco estados, grafos de derivação endereçados por conteúdo, validação de DAG causal e rastreamento de linhagem em menos de 100 ms |
| `skills/claim-evidence-graph` | 1.0.0 | Vinculação determinística de relações entre alegações e evidências, conectando asserções científicas, registros empíricos e proveniência computacional |
| `skills/decision-ledger` | 1.0.0 | Registro de decisões de pesquisa e tentativas falhas: log determinístico e somente de anexação para escolhas científicas, resultados negativos, status da rota / por que a rota foi descontinuada e revisões de conclusões |
| `skills/paper-research` | 1.0.0 | Leitura de artigos e materiais suplementares via DOI, URL ou arquivos locais com validação de campos candidatos, checagens estatísticas, estado persistente de pesquisa, relatórios em chinês vinculados às fontes e comparação entre dois artigos |
| `skills/cross-review-five` | 2.0.0 | Orquestração dinâmica de painel multirrevisor compatível com modelos e subagentes arbitrários (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini etc.): pipeline Sparse Deliberation v2 com atribuição húngara de Kuhn-Munkres, agrupamento de asserções, contestação anônima direcionada e classificação de gravidade P0–P3 |

Existem 22 arquivos de referência Markdown distribuídos entre as quatorze habilidades. Os arquivos de referência são carregados apenas quando necessários.

## Padrões Acadêmicos e Linha de Base Multi-Perfil

Estilos de citação, critérios de relato científico e contratos de metadados variam conforme o periódico de destino, a instituição, a agência de fomento, a área disciplinar e a jurisdição. O repositório estabelece **ISO 690:2021** (Referências bibliográficas), **ISO 5127:2017** (Vocabulário de informação e documentação) e **W3C PROV** (Modelo de dados de proveniência) como referências internacionais, ao lado de perfis regionais (como GB/T 7714-2025 na China continental, UNE-ISO 690:2024 na Espanha e DIN ISO 690:2021 na Alemanha) e normas disciplinares (APA 7.ª ed., IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). As exigências específicas do veículo de publicação prevalecem sobre os perfis padrão. Consulte a [Arquitetura de Padrões Acadêmicos](../../docs/standards/README.md) e o [Guia de Terminologia Natural](../../docs/terminology/README.md).

A consolidação final de integridade valida a coerência entre DOIs e identificadores externos, a exclusividade mútua das marcações booleanas em vereditos quantitativos e o contrato compartilhado de itens pendentes de revisão entre o núcleo e os registros de ingestão. A integridade do cache é reconstruída de forma independente a partir dos envelopes de origem retidos e das vinculações normalizadas, sem depender apenas das listas de mutação do recibo; a remoção simultânea de um registro e de sua declaração de cache não produz uma repetição aceita. Veja o [fechamento dos quatro bloqueios](../../docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Integração e Uso Portátil

### 1. Universal Agent Plugins v1 e Model Context Protocol (MCP)
Este repositório segue a especificação neutra **Agent Plugins v1** (`../../plugin.json`) e disponibiliza ferramentas essenciais de verificação bibliográfica e recálculo estatístico por meio de um **servidor MCP** via stdio (`../../mcp.json` / `../../scripts/mcp_server.py`). É compatível com Claude Code, Cursor, Gemini CLI e qualquer ambiente moderno de agentes. Embora a identidade do repositório seja `academic-research-kernel`, o nome de manifesto `academic-skills` e os aliases de configuração MCP permanecem estáveis para preservar a compatibilidade retroativa.

```bash
# Add as stdio MCP server in your agent harness
uvx academic-research-kernel mcp
```

### 2. Instalação Nativa no Hermes
A partir de uma instalação do Hermes:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Instale as demais habilidades substituindo o nome do diretório no identificador completo. Um tap padrão lê o branch principal do repositório, instalando o conjunto de habilidades listado acima. Para inspecionar um branch de trabalho antes da mesclagem, faça checkout local desse branch e siga as instruções de instalação por diretório local da versão instalada do Hermes; não presuma que o comando tap seleciona branches de revisão.

Habilidades relacionadas verificadas no snapshot upstream `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf e manim-video. Os pacotes huggingface-hub e llama-cpp pertencem ao catálogo opcional e podem exigir instalação separada. Os itens ocr-and-documents e pc-hardware-benchmark não constavam nesse snapshot e não são dependências. Ferramentas de sessão e backends de documentos ou navegador dependem da configuração local.

## Acesso a Fontes de Dados

- Consultas básicas ao OpenAlex podem ser executadas anonimamente com um orçamento diário reduzido. Na documentação verificada em 2026-09-06, o limite é de US$ 0,10/dia no modo anônimo e US$ 1/dia com chave de API gratuita, além do teto de 100 requisições por segundo. Os custos variam conforme o tipo de consulta e não representam acesso ilimitado. Armazene uma chave opcional em `OPENALEX_API_KEY` e utilize `per_page` (máximo de 100) com paginação por cursor.
- O Crossref oferece acesso público a metadados sujeito a controle de taxa. Relações de atualização e sinais do Retraction Watch exigem verificação de DOI e de direção do vínculo; a ausência de registros não prova que um artigo não tenha sido afetado.
- O Unpaywall exige um endereço de e-mail de contato real definido em `UNPAYWALL_EMAIL`. A ausência de localização retornada não comprova a inexistência de cópia em acesso aberto.
- arXiv, Europe PMC, PubMed E-utilities e DOAJ são fontes complementares com políticas próprias e nem todas são acionadas pelos testes padrão. O Semantic Scholar aplica limites anônimos compartilhados e cotas específicas por chave; o acesso à API não garante a disponibilidade do contexto de citação.
- Scite, Dimensions, Scopus, Web of Science e serviços de detecção de IA são integrações externas opcionais. Verifique previamente as permissões da conta, os direitos de API e as cotas vigentes; não há garantia de faixa gratuita universal nem de preços fixos.

Consulte a documentação sobre [autenticação no OpenAlex](https://help.openalex.org/api/authentication/), [orçamentos e custos de consulta](https://help.openalex.org/api/llm-quick-reference/) e [filtros de atualização do Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Ingestão determinística e núcleo público

A camada de ingestão fornece `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 adaptadores (correspondentes às 14 habilidades mais o fallback opaco) e 12 ferramentas MCP stdio sem estado. Os registros de ingestão aceitos vinculam cada mutação semântica retida por tipo, identidade e resumo SHA-256 canônico: objetos, registros de relações entre alegações e evidências (CEG), entradas do registro de decisões de pesquisa e tentativas falhas, itens pendentes de revisão, comprovantes físicos e registros de artefatos. A repetição via cache valida esses compromissos de maneira independente dos hashes de instantâneo de transporte. Registros vazios são válidos e lotes atômicos que falham não deixam estado parcial.

A autoridade sobre o conteúdo de linhagem é explícita e transmitida fora de banda. Chamadores Python confiáveis fornecem `LineageVerificationContext` ao reproduzir recibos ou instantâneos serializados; chamadores MCP podem enviar bytes de conteúdo dentro do limite estabelecido, mas nunca uma raiz do sistema de arquivos hospedeiro. O orçamento padrão de conteúdo é de 10 MiB, podendo um host confiável autorizar explicitamente artefatos maiores sob a mesma política entre produtor e verificador. Sem autoridade de conteúdo, uma alegação `fully_verified` não pode ser reproduzida de modo independente e retorna um resultado estruturado de verificação inválida. Textos não estruturados permanecem opacos, divergências permanecem visíveis e os pesquisadores mantêm o controle sobre confirmações, encerramento ou reabertura de rotas, roteamento e julgamentos de validade científica.

Consulte a [arquitetura do núcleo](../../docs/kernel-architecture.md) para detalhes sobre contratos e regras de compatibilidade. Os pontos de verificação de distribuição e publicação estão registrados no [guia de lançamento](../../docs/distribution-release.md). Os arquivos README em inglês e chinês simplificado são mantidos em sincronia imediata, enquanto o estado das demais traduções consta de forma explícita no [manifesto de sincronização](../../docs/i18n/manifest.json). A identidade da versão candidata, a verificação de CI no commit exato e o histórico acumulado de revisão e mesclagem estão documentados no [registro de fechamento](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Validação

Utilize um ambiente Python dedicado. As bibliotecas de execução variam conforme a tarefa e não têm instalação garantida no Hermes. As dependências de QA são mais amplas para permitir a execução de todos os exemplos demarcados:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

O script de QA valida metadados, referências locais, padrões de caminhos pessoais ou segredos conhecidos, sintaxe Python e blocos de código executáveis demarcados. Cada exemplo `smoke` roda sem alterações em um subprocesso limpo. Exemplos que geram gráficos aceitam `PLOT_DIR` (padrão `~/plots`, expandido explicitamente), usando diretórios temporários durante os testes. Blocos Python sem classificação são rejeitados; blocos `fragment:` passam por verificação sintática, mas exigem variáveis de entrada nomeadas e não são executados isoladamente. Blocos `external-test:` são executados apenas pelo comando manual de verificação externa, que retorna `0` quando as verificações configuradas passam, `1` em falhas de código, esquema ou identidade e `2` em indisponibilidade de rede, autenticação ou cota, mantendo serviços opcionais não configurados como `SKIP`.

Os testes de autoria fixados do Hermes são reutilizados sem alterar suas regras individuais por habilidade. Verificações globais da distribuição completa do Hermes não se aplicam a este repositório; nossa suíte valida as quatorze habilidades e resolve referências contra o catálogo fixado de pacotes integrados e opcionais. Isso não substitui um teste completo de instalação do Hermes. O ambiente de CI utiliza rede apenas para instalar dependências, e os testes regulares de revisão não consultam APIs acadêmicas externas.

O CI executa a suíte completa de QA em Linux x86_64 (Python 3.10–3.14), Linux ARM64 (`ubuntu-24.04-arm`), Ubuntu 26.04 preview canary (`ubuntu-26.04` e `ubuntu-26.04-arm`), Windows x86_64, Windows ARM64 (`windows-11-arm`), macOS ARM64 (`macos-latest`) e macOS Intel (`macos-15-intel`), incluindo validação canary contínua contra o repositório upstream. A versão base histórica aprovou 1165 testes locais. Os resultados atuais de correção e os limites de cobertura estão registrados no [relatório de reparo de corretude](../../docs/maintenance/correctness-repair-20261008.md), e as evidências remotas identificam separadamente o commit `HEAD` testado. Um fluxo adicional de integração via tap é executado a cada envio ao branch `main`, instalando a revisão fixada do Hermes descrita em `tests/upstream/provenance.json` e testando os comandos `tap add`, `search`, `install` e `list` contra este repositório. Versões exatas, verificações e limitações constam na [auditoria do projeto](../../docs/project-lineage-audit-20260920.md).

O diretório [tools/longtail/](../../tools/longtail/README.md) mantém o gerador determinístico de fatores de cauda longa: 4096 candidatos gerados por semente SHA-256, 30 cenários selecionados e um relatório de cobertura de verificação calculado automaticamente. O modelo v3 contabiliza separadamente famílias de capacidades (E01), as 14 habilidades reais do repositório (E02) e objetivos de tarefa (E03). Cada cenário associa uma habilidade principal, um objetivo compatível e capacidades correspondentes; cada habilidade deve aparecer ao menos duas vezes sob dois objetivos distintos, incluindo seu objetivo principal declarado. Divergências em relação aos diretórios de habilidades interrompem a validação. A expansão semântica (cadeias de tarefas, oráculos e injeção de eventos executados) permanece uma etapa distinta; a cobertura fatorial não equivale à cobertura de execução de ponta a ponta.

O módulo `scripts/scfabric/` implementa o conjunto de ferramentas de cálculo científico e estatística: sondagem de hardware, catálogo de backends com filtros de tipo de dados (`dtype`), cinco perfis de carga de trabalho, benchmark pareado com admissão por paridade numérica e emissão de `ComputeReceipt`. As medições iniciais estão documentadas em [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md); a regra geral adota CPU por padrão e habilita aceleradores apenas mediante comprovante verificado.

## Pesquisar um artigo com um Agente local

Instale `academic-research-kernel[research]==2.1.0` e exporte o fluxo de trabalho empacotado:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Permita que o Work ou outro Agente local compatível leia o arquivo `SKILL.md` exportado e solicite:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Forneça apenas o DOI, o link público ou o pacote local de arquivos. Para analisar dois artigos simultaneamente, peça ao Agente que compare dados, métodos, condições de avaliação e resultados, explicando o que é diretamente comparável. O Agente conduzirá na mesma tarefa a leitura do texto original, a validação de campos candidatos, os recálculos estatísticos, a ingestão no núcleo, a geração do relatório e a revisão independente das fontes. A superfície MCP existente preserva suas 12 ferramentas; a nova orquestração opera por meio da CLI e da habilidade portátil.

As etapas efetivas do programa são:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

O comando `prepare` obtém e analisa o material em um manifesto, hashes de origem e segmentos localizados. O comando `finish` valida a extração estruturada produzida pelo Agente e recalcula alegações elegíveis de testes t/valores p, tamanhos de efeito entre dois grupos e contagens ou porcentagens usando as ferramentas estatísticas existentes, salvando em seguida o estado do núcleo e relatórios em Markdown e HTML em chinês. O comando `compare` valida a avaliação explícita do Agente sobre condições comparáveis entre estudos. Esses comandos não embutem um modelo residente próprio: a leitura semântica é realizada pelo Agente em uso seguindo as instruções de [paper-research](../../skills/paper-research/SKILL.md). Os arquivos originais salvos e os instantâneos de extração permitem repetição determinística offline, mantendo a obtenção via rede e uma nova leitura semântica como operações identificadas separadamente.

## Corretude da versão 2.0.1 e verificação de distribuição

O lançamento 2.0.1 incorpora reparos de precisão estatística e conformidade de protocolo. A ferramenta pública `academic_recompute_statistics` expõe valores p de testes t e medidas `d` de Cohen / `g` de Hedges para dois grupos, enquanto intervalos de confiança e razões de chances ou riscos (`OR/RR`) permanecem como funções Python de nível inferior. Informe `p_value_literal` (por exemplo, `"1.0e-5"`) ou `p_value_decimals` quando a precisão exata do relato for relevante. Valores literais preservam zeros à direita; entradas puramente numéricas mantêm apenas sua representação numérica padrão, e fontes de precisão conflitantes falham de forma explícita. As comparações por arredondamento (`round-half-up`) incluem o limite inferior e excluem o limite superior. Uma divergência numérica comum constitui um resultado científico válido, ao passo que cálculos inválidos ou parcialmente malsucedidos definem `isError`.

As verificações de retratação registram a observação atual (`True`/`False`/`unknown`) separadamente do último valor confirmado. Uma reserva breve antes da consulta ordena observações para o mesmo DOI e preserva atualizações de outros DOIs. Observações atuais e confirmações históricas possuem versões distintas: uma confirmação tardia pode enriquecer o histórico retido enquanto um estado `unknown` mais recente permanece explicitamente registrado como não verificado na checagem atual. As respostas HTTP simuladas nas cadeias de regressão são identificadas como dados de teste.

O servidor MCP responde a `ping`, permanece silencioso diante de notificações válidas (incluindo `notifications/cancelled`) e mantém a sessão stdio ativa após entradas inválidas. A implementação síncrona não anuncia cancelamento preemptivo. O tratamento de mensagens segue o [contrato de mensagens MCP](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) e a [especificação de ping](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Construa e verifique as distribuições desta cópia de trabalho em um ambiente isolado:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

A opção `--source-checks` extrai o pacote `sdist` candidato sem modificações fora da árvore do repositório, define `ARK_REPO` e `ARK_SDIST` para esse candidato e executa seus testes, verificações estáticas de QA, blocos de código executáveis e checagem de sincronização i18n. As instalações via `wheel` e `sdist` utilizam ambientes limpos independentes, e o `uvx` emprega o `wheel` local com cache isolado. O relatório final registra hashes dos artefatos e caminhos reais de importação. Verificações agendadas leves do Hermes (`pinned` e `latest`) relatam separadamente o commit SHA testado. Os arquivos JSON de contrato externo e os resumos de execução utilizam os estados `healthy`, `degraded` e `failed`, mantendo sondagens ignoradas explicitamente identificadas.

## Documentos de pesquisa e planejamento

Estes dois documentos são referências exploratórias de planejamento e não constituem um roteiro vinculante. A numeração das direções é recalculada a partir do agrupamento armazenado em `docs/direction-primitive-mapping.json`.

- [Pain Atlas v0 (Inglês)](../../docs/pain-atlas-v0.en.md), [中文版](../../docs/pain-atlas-v0.zh.md): pontos de atrito ao longo do ciclo de vida do trabalho acadêmico, com estados de verificação associados às alegações quantitativas.
- [Research Plan v0 (Inglês)](../../docs/research-plan-v0.en.md), [中文版](../../docs/research-plan-v0.zh.md): o modelo Research Object, áreas de competência fundamentais, direções candidatas e a matriz de decomposição fatorial da primeira fase.
