# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

Conjunto determinista de herramientas de gestión y verificación del estado de investigación académica para flujos de trabajo con agentes, independiente del entorno de ejecución. Mediante una incorporación determinista de artefactos de investigación y un servidor universal Model Context Protocol (MCP), unifica la identificación y trazabilidad de objetos de investigación, los registros de evidencia y verificación empírica, los vínculos entre afirmaciones y evidencias, y un registro de decisiones de investigación y ensayos fallidos de solo anexado. 14 competencias académicas especializadas actúan como productoras y consumidoras del estado de investigación verificado, con compatibilidad nativa para Claude Code, Cursor, Codex, Gemini CLI y Hermes Agent. El alcance de validación y las limitaciones de los servicios externos constan en [la auditoría](docs/project-lineage-audit-20260920.md).

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Oferta actual: [Source Lineage License 1.0](LICENSE).

## Inicio rápido

Ejecute la versión 2.2.0 con [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx academic-research-kernel@2.2.0 mcp
```

La [versión 2.2.0](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.2.0) registra los hashes de distribución y el estado de publicación. El paquete wheel publicado también puede ejecutarse localmente con `uvx --from ./academic_research_kernel-2.2.0-py3-none-any.whl academic-research-kernel mcp`. Se admite Python 3.10–3.14; `uvx --python 3.12` selecciona explícitamente un intérprete compatible. Las 12 herramientas deterministas, incluido el cálculo estadístico, forman parte de la instalación base.

## Verificar la instalación

```bash
uvx academic-research-kernel@2.2.0 doctor
uvx academic-research-kernel@2.2.0 --version
```

El diagnóstico sin conexión comprueba las dependencias, los esquemas y las 12 definiciones de herramientas. Los servicios externos opcionales pueden permanecer sin configurar. Utilice `doctor --json` para obtener una salida legible por máquina.

## Instalación del paquete

```bash
uv tool install academic-research-kernel==2.2.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Alternativamente, puede instalarlo con `pipx install academic-research-kernel==2.2.0` o mediante `python -m pip install academic-research-kernel==2.2.0` dentro de un entorno virtual compatible. `[full]` añade bibliotecas para ejemplos avanzados de cálculo científico; `[qa]` añade las herramientas de validación del repositorio, incluido el analizador de PDF. `[research]` incorpora `pypdf==6.19.0` y `fonttools==4.65.0` para garantizar una decodificación uniforme de fuentes PDF en instalaciones limpias (ambos compatibles con Python 3.10). La lectura de HTML/XML estructurado y de archivos DOCX/XLSX acotados utiliza la biblioteca estándar. Los backends de GPU y los servicios de pago siguen siendo opcionales.

## Hermes

Asegúrese de que `uv` se encuentre en el PATH del proceso de Hermes y, a continuación, instale y habilite explícitamente el complemento portátil:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

Se conserva el identificador existente `academic-skills`, que ahora abarca 14 competencias, incluida `paper-research`. El archivo `mcp.json` del complemento invoca `uv run --frozen --no-dev --no-editable` con Python 3.12 y el `uv.lock` del repositorio; su entorno de ejecución reside aislado bajo `${PLUGIN_DATA}/runtime`. En el primer uso prepara las dependencias sin tomar prestados paquetes Python de Hermes ni del sistema, por lo que requiere conexión de red inicial para obtener los paquetes o el intérprete que falten. El método anterior mediante tap exclusivo de competencias sigue estando admitido (véase la sección de integración y uso portátil más abajo).

## Ejecución desde el código fuente

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Consulte [distribución y publicación](docs/distribution-release.md) para conocer la clasificación de dependencias, la reproducción, la identidad de la versión, los puntos de control de publicación y el alcance de validación.

## Licencia

La instantánea que contiene este aviso aplica la **Source Lineage License 1.0** al material cubierto y a los derechos identificados en [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md). El primer commit SLL con su árbol, y el commit posterior de registro de frontera, se distinguen en [LICENSE-HISTORY.md](LICENSE-HISTORY.md) y [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md). Las instantáneas posteriores a esa transición registrada que conservan este aviso llevan la misma oferta.

Las instantáneas históricas hasta `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` se distribuyeron bajo licencia MIT, sujetas a las condiciones aplicables a esas copias. Los destinatarios conservan permisos MIT válidos y no tienen que migrar a SLL. El [antiguo texto MIT del proyecto](LICENSES/MIT-pre-SLL.txt) se conserva; [tests/upstream/LICENSE](tests/upstream/LICENSE) y su procedencia de terceros permanecen sin cambios. La nueva oferta raíz no borra esos derechos.

SLL permite ampliamente el uso, el estudio, la modificación, el uso comercial, la distribución y las adiciones propietarias, sujetos a las condiciones de licencia, aviso y linaje de fuentes aplicables. No es copyleft y no exige divulgación de código fuente. Un servicio de red puro sin suministro de copias no activa por sí solo la condición de aviso de linaje del servicio núcleo. No hay concesión expresa de patentes. El material de terceros sigue bajo sus propios términos. El texto inglés original de la [LICENSE](LICENSE) prevalece sobre este resumen informativo; `LicenseRef-Source-Lineage-1.0` es una referencia local, no una asignación SPDX, y no se reclama aprobación OSI. La [admisión de contribuciones](CONTRIBUTING.md) es independiente de los permisos de licencia posteriores.

## Competencias

| Competencia | Versión | Función |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Contrastar identidad y recuentos de citas por fuente; inspeccionar señales de actualización y retractación; localizar texto en acceso abierto y verificar la identidad de los PDF |
| `skills/literature-analysis` | 1.3.0 | Doce flujos: similitud temática, solapamiento local de texto, contraevidencia, perfiles de autores, revisión simulada, comprobación de falacias, matriz de revisión, revistas candidatas, BibTeX, lectura bilingüe, cribado de lagunas, reproducción |
| `skills/academic-writing` | 1.1.1 | Edición académica, pautas de citación (ISO 690, APA, MLA, Chicago, IEEE, AMA y perfiles regionales), directrices para autores, servicios opcionales de detección, materiales de envío y requisitos institucionales |
| `skills/math-computation` | 1.2.1 | Enrutamiento de dominio y tarea existente con ejemplos numéricos y estadísticos corregidos; cuatro archivos de referencia por dominio |
| `skills/quantitative-paper-audit` | 1.1.0 | Recalcular las estadísticas declaradas (tamaño del efecto, valores p, intervalos de confianza, OR/RR, potencia alcanzada) y detectar discrepancias numéricas |
| `skills/research-reproducibility` | 1.0.1 | Cadena de auditoría de reproducción en catorce etapas con listas de verificación estructuradas, cinco niveles de hechos y registros de auditoría reproducibles |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Registros de búsqueda PRISMA, registro de cribado de literatura, conversión de tamaños del efecto, heterogeneidad, agrupación de efectos fijos y aleatorios, diagnósticos de sensibilidad y sesgo de publicación |
| `skills/literature-watch` | 1.1.0 | Plano semanal: vigilar temas, autores y obras que citan DOI en OpenAlex y Crossref; deduplicar y notificar solo novedades |
| `skills/retraction-watch` | 1.1.0 | Plano semanal: reverificar una lista de DOI contra OpenAlex `is_retracted` y los registros de actualización de Crossref (señales `update-to`); notificar solo cambios de estado |
| `skills/research-object-identity` | 1.1.0 | Identificación determinista de recursos de investigación y procedencia / trazabilidad: normalización de identificadores, verificación de 5 estados, grafo de derivación direccionado por contenido, validación de DAG causal y rastreo fuera de línea en menos de 100 ms |
| `skills/claim-evidence-graph` | 1.0.0 | Vínculos entre afirmaciones y evidencias: conexión determinista de afirmaciones científicas, registros de evidencia / verificación y procedencia computacional |
| `skills/decision-ledger` | 1.0.0 | Registro de decisiones de investigación y ensayos fallidos: registro determinista de solo anexado de decisiones, ensayos fallidos (resultados negativos), estado de la ruta / por qué se detuvo esta vía y revisiones de conclusiones |
| `skills/paper-research` | 1.0.0 | Lectura de artículos y suplementos mediante DOI, URL o paquete local con candidatos de campo validados, comprobaciones estadísticas, estado de investigación persistente, informes en chino vinculados a las fuentes y comparación de dos artículos |
| `skills/cross-review-five` | 2.0.0 | Orquestación dinámica de panel multirrevisor compatible con modelos y subagentes arbitrarios (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini, etc.): canalización v2 Sparse Deliberation con asignación húngara de Kuhn-Munkres, agrupación de afirmaciones, interpelación anónima dirigida y clasificación de severidad P0–P3 |

Las catorce competencias incluyen 22 archivos de referencia Markdown, cargados solo cuando se necesitan.

## Estándares académicos y marco multiperfil

Los estilos de citación, los criterios de presentación de informes y los contratos de metadatos dependen de la revista de destino, la institución, el organismo de financiación, la disciplina y la jurisdicción. El repositorio establece **ISO 690:2021** (referencias bibliográficas), **ISO 5127:2017** (vocabulario de información y documentación) y **W3C PROV** (modelo de datos de procedencia) como bases internacionales, junto con perfiles regionales (como UNE-ISO 690:2024 en España, GB/T 7714-2025 en China continental, DIN ISO 690:2021 en Alemania) y normas disciplinarias (APA 7.ª ed., IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Los requisitos de la entidad o revista de destino tienen siempre prioridad sobre los perfiles predeterminados. Consulte la [Arquitectura de estándares académicos](docs/standards/README.md) y la [Guía de terminología natural](docs/terminology/README.md).

La versión 2.2.0 valida la coherencia de los DOI e identificadores externos, los indicadores booleanos mutuamente excluyentes de veredicto cuantitativo y el contrato de elementos pendientes de verificación compartido entre el núcleo y los registros de verificación. La integridad de la caché se reconstruye a partir de los sobres fuente conservados y las vinculaciones normalizadas, con independencia de las listas de mutaciones del registro; eliminar simultáneamente un registro y su declaración de caché no puede producir una repetición aceptada. Consulte el [cierre de los cuatro bloqueos](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Integración y uso portátil

### 1. Agent Plugins v1 universal y Model Context Protocol (MCP)
Este repositorio cumple con la especificación neutral **Agent Plugins v1** (`plugin.json`) y expone las herramientas principales de verificación académica y recálculo estadístico a través de un **servidor MCP** stdio (`mcp.json` / `scripts/mcp_server.py`). Compatible con Claude Code, Cursor, Gemini CLI y cualquier entorno moderno de agentes. (Nota: aunque la identidad del repositorio es `academic-research-kernel`, el nombre del manifiesto del complemento `academic-skills` y los alias de configuración MCP se mantienen estables por compatibilidad regresiva.)

```bash
# Añadir como servidor MCP stdio en su entorno de agentes
uvx academic-research-kernel mcp
```

### 2. Instalación nativa en Hermes
Desde una instalación de Hermes:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Instale las demás competencias sustituyendo su nombre de directorio en el identificador completo. Un tap normal lee la rama por defecto, de modo que un tap nuevo instala el conjunto anterior. Para inspeccionar una rama de trabajo antes de fusionar, extraiga esa rama localmente y siga las instrucciones de instalación por carpeta local de la versión de Hermes instalada. No asuma que el comando tap selecciona automáticamente una rama de pull request.

Competencias relacionadas agrupadas, verificadas contra el upstream `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video. huggingface-hub y llama-cpp están en el catálogo opcional y pueden requerir instalación. ocr-and-documents y pc-hardware-benchmark no estaban en esa instantánea y no son dependencias. Las herramientas de sesión y los backends de documentos y navegador dependen de la configuración local.

## Acceso a fuentes de datos

- Las consultas básicas de OpenAlex pueden ejecutarse de forma anónima con un presupuesto diario menor. Los documentos vigentes al 2026-09-06 indican 0,10 USD/día anónimo y 1 USD/día con clave API gratuita, más un tope de 100 peticiones/segundo. Los costes varían según el tipo de consulta; no es acceso ilimitado. Guarde una clave opcional en `OPENALEX_API_KEY`. Use `per_page` (máximo 100) y paginación por cursor.
- Crossref ofrece acceso público a metadatos con limitación de velocidad. Las relaciones de actualización y las señales de Retraction Watch exigen comprobaciones de DOI y dirección; la ausencia de registros no prueba que un artículo no esté afectado.
- Unpaywall exige un correo de contacto real en `UNPAYWALL_EMAIL`. La ausencia de ubicación no prueba que no exista copia en acceso abierto.
- arXiv, Europe PMC, PubMed E-utilities y DOAJ son fuentes complementarias con sus propias políticas. No todas se ejercitan en las pruebas por defecto. Semantic Scholar tiene límites anónimos compartidos y límites de clave asignados por separado; el acceso no garantiza disponibilidad del contexto de citas.
- Scite, Dimensions, Scopus, Web of Science y los productos de detección de IA son servicios externos opcionales. Compruebe los derechos y cupos actuales de cuenta y API antes de usarlos; no se promete un nivel gratuito universal ni precios fijos.

Véanse [la autenticación de OpenAlex](https://help.openalex.org/api/authentication/), [los presupuestos y costes de consulta](https://help.openalex.org/api/llm-quick-reference/) y [los filtros de actualización de Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Incorporación determinista e interfaz pública del núcleo

La versión 2.2.0 proporciona `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 adaptadores (las 14 competencias más el respaldo opaco) y 12 herramientas MCP stdio sin estado. Los registros de incorporación aceptados vinculan cada mutación semántica conservada por tipo, identidad y SHA-256 canónico: objetos de investigación, registros de vínculos entre afirmaciones y evidencias, entradas del registro de decisiones de investigación y ensayos fallidos, elementos pendientes de verificación, registros físicos de verificación y registros de artefactos. La repetición de caché comprueba esos compromisos con independencia de los hashes de las instantáneas de transporte. Los registros vacíos son válidos; los lotes atómicos fallidos no dejan estado parcial.

La autorización de lectura del contenido de procedencia es explícita y fuera de banda. Los invocadores de Python de confianza pasan `LineageVerificationContext` al reproducir registros de verificación o instantáneas serializados; los invocadores MCP pueden suministrar bytes de contenido acotados, pero nunca una raíz del sistema de archivos anfitrión. El presupuesto de contenido predeterminado es de 10 MiB; un anfitrión de confianza puede autorizar explícitamente artefactos mayores bajo la misma política entre productor y verificador. Sin autorización de contenido, una afirmación `fully_verified` no puede reproducirse de forma independiente y devuelve un resultado estructurado de verificación no válida. El texto no estructurado permanece opaco, las discrepancias siguen siendo visibles y los investigadores conservan el control sobre las confirmaciones, la detención o reapertura de vías, el enrutamiento y los juicios científicos.

Consulte [la arquitectura del núcleo](docs/kernel-architecture.md) para ver los contratos y la compatibilidad. Los puntos de control de distribución y publicación constan en [la guía de publicación](docs/distribution-release.md). Los README en inglés y en chino simplificado están al día; el estado de las demás traducciones se detalla en [el manifiesto](docs/i18n/manifest.json). La identidad del candidato final, la CI sobre HEAD exacto, la revisión acumulada y la evidencia de fusión se registran en [el acta de cierre](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Validación

Utilice un entorno Python dedicado. Las bibliotecas de ejecución son específicas de cada tarea y no se garantiza su instalación en Hermes. Las dependencias de QA son más amplias para que todos los ejemplos marcados se ejecuten:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

QA valida metadatos, referencias, patrones de rutas personales y secretos conocidos, sintaxis Python y bloques de código ejecutables marcados. Cada ejemplo smoke se ejecuta sin cambios en un subproceso nuevo. Los ejemplos de trazado aceptan `PLOT_DIR` (por defecto `~/plots`, expandido explícitamente); las pruebas usan un directorio temporal. Los bloques Python sin clasificar se rechazan; los bloques `fragment:` se comprueban sintácticamente pero exigen entradas con nombre y no se ejecutan solos. Los bloques `external-test:` solo se ejecutan mediante el comando externo manual. Devuelve 0 en comprobaciones configuradas superadas, 1 en fallos de código/esquema/identidad y 2 en indisponibilidad de transporte/autenticación/cupo; los servicios opcionales sin configurar permanecen SKIP.

Las pruebas de autoría de Hermes fijadas se reutilizan sin cambiar sus reglas por competencia. Las comprobaciones poblacionales de la distribución completa del upstream no se aplican a este tap; nuestro banco de pruebas comprueba catorce competencias y resuelve referencias contra el catálogo agrupado y opcional fijado. Esto no es una prueba completa de instalación de Hermes. La CI usa la red solo para instalar dependencias; las pruebas ordinarias no llaman a API académicas.

La CI ejecuta la suite QA completa en Linux x86_64 (Python 3.10–3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 Preview-Canary (ubuntu-26.04 & ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest) y macOS Intel (macos-15-intel), con validación Canary en vivo de la rama upstream. El candidato histórico de referencia superó 1165 pruebas locales; los resultados actuales de reparación y los límites de cobertura constan en [la reparación de corrección](docs/maintenance/correctness-repair-20261008.md), donde la evidencia remota identifica por separado el HEAD probado. Un flujo de integración tap separado se ejecuta en las subidas a main: instala el checkout de Hermes fijado registrado en tests/upstream/provenance.json y ejercita tap add, search, install y list contra este repositorio. Las versiones, comprobaciones y limitaciones exactas constan en [la auditoría](docs/project-lineage-audit-20260920.md).

[tools/longtail/](tools/longtail/README.md) aloja el generador determinista de factores de cola larga: 4096 candidatos con semilla SHA256, 30 escenarios seleccionados y un informe de cobertura de verificación calculado por máquina. El modelo v3 contabiliza por separado las familias de capacidades (E01), las 14 competencias reales del repositorio (E02) y los objetivos de tarea (E03). Cada escenario tiene una competencia principal, un objetivo de tarea admitido y capacidades compatibles; cada competencia debe aparecer al menos dos veces bajo dos objetivos distintos, incluido su objetivo principal declarado. Cualquier desviación respecto a los directorios de competencias hace fallar la validación. La expansión semántica (cadenas de tareas, oráculos e inyección de eventos ejecutados) permanece como una etapa separada; la cobertura de factores no demuestra la cobertura de ejecución de los flujos de trabajo.

scripts/scfabric/ constituye la capa de ejecución del conjunto de herramientas de cálculo científico y estadística: sonda de hardware, catálogo de backends con filtros de tipo de dato, cinco perfiles de carga de trabajo, banco de pruebas emparejado con admisión por paridad y ComputeReceipt. Las primeras mediciones en esta máquina se encuentran en [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md); la regla general es usar CPU por defecto, y acelerador solo con un registro ComputeReceipt.

## Investigar un artículo con un Agente local

Instale `academic-research-kernel[research]==2.2.0` y exporte el flujo de trabajo empaquetado:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Permita que Work o un Agente local compatible lea ese archivo `SKILL.md` exportado y pídale:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Proporcione únicamente el DOI, el enlace público o el paquete local de archivos. Para dos artículos, pídale que compare los datos, los métodos, las condiciones de evaluación y los resultados, explicando qué elementos son directamente comparables. El Agente continúa dentro de la misma tarea con la lectura del texto original, la validación de candidatos, el cálculo, la incorporación, la generación del informe y la revisión independiente de fuentes. La superficie MCP existente conserva sus 12 herramientas; la nueva orquestación reside en la CLI y en la competencia portátil.

Las etapas reales del programa son:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` obtiene y analiza el material generando un manifiesto, hashes de origen y segmentos localizados. `finish` valida la extracción producida por el Agente, recalcula las afirmaciones elegibles de valores t/p, tamaños del efecto de dos grupos y recuentos/porcentajes utilizando las herramientas estadísticas existentes, y guarda el estado del núcleo junto con los informes Markdown/HTML en chino. `compare` valida la evaluación explícita del Agente sobre las condiciones comparables. Estos comandos no integran un modelo Work residente: la lectura semántica la realiza el Agente actual siguiendo [paper-research](skills/paper-research/SKILL.md). Los archivos originales guardados y las instantáneas de extracción permiten una repetición determinista sin conexión. La obtención por red y una nueva lectura semántica permanecen como operaciones identificadas por separado.

## 2.0.1 Verificación de corrección y distribución

Desde la versión 2.0.1, la herramienta pública `academic_recompute_statistics` expone valores p de pruebas t y d de Cohen / g de Hedges para dos grupos, mientras que los intervalos de confianza (CI) y OR/RR permanecen como funciones de Python de nivel inferior. Suministre `p_value_literal` (por ejemplo, `"1.0e-5"`) o `p_value_decimals` cuando importe la precisión declarada en el artículo. Los literales conservan los ceros finales; las entradas numéricas conservan únicamente su representación numérica. Las fuentes de precisión en conflicto fallan explícitamente. Las comparaciones de redondeo (round-half-up) incluyen el límite inferior de redondeo y excluyen el límite superior. Una discrepancia numérica ordinaria es un resultado científico válido; los cálculos no válidos o parcialmente fallidos activan `isError`.

Las comprobaciones de retractación registran la observación actual (`True` / `False` / `unknown`) por separado del último valor conocido. Una breve reserva previa a la consulta ordena las observaciones de un mismo DOI y preserva las actualizaciones de otros DOI. Las observaciones actuales y las confirmaciones históricas tienen versiones separadas: una confirmación tardía puede enriquecer el historial conservado mientras que un `unknown` más reciente permanece explícitamente como no verificado para la comprobación actual. Los fixtures HTTP en las cadenas de regresión están etiquetados como datos de prueba.

El servidor MCP responde a `ping`, permanece en silencio ante notificaciones válidas (incluida `notifications/cancelled`) y mantiene activa la sesión stdio tras una entrada no válida. La implementación síncrona no anuncia cancelación preventiva. El manejo de mensajes sigue el [contrato de mensajes MCP](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) y la [especificación de ping](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Compile y verifique las distribuciones de esta copia de trabajo con un entorno aislado:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` extrae el sdist candidato sin cambios fuera del árbol de trabajo, establece `ARK_REPO` y `ARK_SDIST` en ese candidato y ejecuta sus pruebas, la QA estática, los bloques de código ejecutables y la comprobación i18n. Las instalaciones de wheel y sdist utilizan cada una un entorno limpio; `uvx` usa el wheel local con una caché independiente. El informe registra los hashes de los artefactos y las rutas de importación instaladas. Las comprobaciones ligeras programadas de Hermes (fijada y más reciente) informan por separado del SHA probado. Los archivos JSON de contrato externo y los resúmenes de ejecución utilizan `healthy`, `degraded` y `failed`; las sondas omitidas permanecen explícitas.

## Documentos de investigación y planificación

Estos dos documentos son referencias exploratorias de planificación, no una hoja de ruta vinculante. Sus números de dirección se recalculan a partir de la agrupación almacenada en docs/direction-primitive-mapping.json.

- [Atlas de puntos de fricción v0 (inglés)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md): puntos de fricción del ciclo de vida del trabajo académico, con estado de verificación adjunto a las afirmaciones cuantitativas.
- [Plan de investigación v0 (inglés)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md): el modelo Research Object, áreas de competencia fundamentales, direcciones candidatas y la matriz de descomposición factorial de la primera fase.
