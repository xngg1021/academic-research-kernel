# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

Núcleo de investigación académica neutral respecto al entorno y suite de deliberación multiagente. Proporciona 13 herramientas de verificación y habilidades académicas con puntos de entrada portátiles Agent Plugins v1 y MCP, así como integración nativa para Hermes Agent, Claude Code, Cursor y subagentes CLI personalizados. Cubren verificación de fuentes, análisis de literatura, redacción académica, cálculo numérico, auditoría cuantitativa de artículos, auditorías de reproducibilidad, revisiones sistemáticas y metaanálisis, identidad y linaje de objetos de investigación, orquestación de revisiones entre modelos, más dos automatizaciones de vigilancia semanal. El repositorio incluye comprobaciones de ejemplos ejecutables; el alcance de validación y las limitaciones de servicios externos constan en [la auditoría](docs/audit-20260906.md).

Autor: Junfu Shi (SJF, xngg1021), Hermes Agent. Oferta actual: [Source Lineage License 1.0](LICENSE).

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
| `skills/systematic-review-meta-analysis` | 1.0.1 | Registros de búsqueda PRISMA, registros de cribado de literatura, conversión de tamaños del efecto, heterogeneidad, agrupación de efectos fijos y aleatorios, diagnósticos de sensibilidad y sesgo de publicación |
| `skills/literature-watch` | 1.1.0 | Plano semanal: vigilar temas, autores y obras que citan DOI en OpenAlex y Crossref; deduplicar y notificar solo novedades |
| `skills/retraction-watch` | 1.1.0 | Plano semanal: reverificar una lista de DOI contra OpenAlex is_retracted y los registros de actualización de Crossref (señales update-to); notificar solo cambios de estado |
| `skills/research-object-identity` | 1.1.0 | Identificación de recursos de investigación y trazabilidad determinista: normalización de identificadores, veredicto de 5 estados, grafo de derivación direccionado por contenido, validación de DAG causal y rastreo fuera de línea |
| `skills/claim-evidence-graph` | 1.0.0 | Vínculos deterministas entre afirmaciones y evidencias: conexión de afirmaciones científicas, registros de evidencia empírica y procedencia |
| `skills/decision-ledger` | 1.0.0 | Registro de decisiones de investigación y ensayos fallidos: registro determinista de solo anexado de decisiones, ensayos fallidos, motivos de abandono de vías y revisiones de conclusiones |
| `skills/cross-review-five` | 2.0.0 | Panel dinámico de revisión multi-modelo y subagentes (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini, etc.): canalización v2 Sparse Deliberation de 4 fases con asignación húngara de Kuhn-Munkres y severidades P0-P3 |

Las trece competencias incluyen 21 archivos de referencia Markdown, cargados solo cuando se necesitan.

## Estándares académicos y marco multiperfil

Los estilos de citación, las directrices de comunicación y los contratos de metadatos dependen de la revista de destino, el organismo de financiación, la disciplina y la jurisdicción. El repositorio establece **ISO 690:2021** (referencias bibliográficas y citas), **ISO 5127:2017** (vocabulario de información y documentación) y **W3C PROV** (modelo de datos de procedencia) como referencias base internacionales, complementadas con perfiles regionales (como UNE-ISO 690:2024 en España, GB/T 7714-2025 en China continental, DIN ISO 690 en Alemania) y normas disciplinarias (APA 7.ª ed., IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Las directrices de la entidad o revista de destino tienen siempre prioridad. Consulte la [Arquitectura de estándares académicos](docs/standards/README.md) y la [Guía de terminología natural](docs/terminology/README.md).

## Integración e Instalación

### 1. Agent Plugins v1 y Servidor MCP
Este repositorio cumple con la especificación neutra **Agent Plugins v1** (`plugin.json`) y expone las herramientas esenciales de verificación académica y recálculo estadístico a través de un **servidor MCP** stdio (`mcp.json` / `python scripts/mcp_server.py`). Compatible con Claude Code, Cursor, Gemini CLI y cualquier entorno moderno de agentes.

```bash
# Añadir como servidor MCP stdio en su entorno de agentes
python scripts/mcp_server.py
```

### 2. Instalación en Hermes

La detección de tap actual inspecciona los subdirectorios inmediatos de `skills/`. Cada competencia vive por tanto directamente bajo esa raíz. Desde una instalación de Hermes:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Instalar las demás sustituyendo su nombre de directorio en el identificador completo. Un tap normal lee la rama por defecto, de modo que un tap nuevo instala el conjunto anterior. Para inspeccionar una rama de trabajo antes de fusionar, extraer esa rama localmente y seguir las instrucciones de instalación por carpeta local de la versión de Hermes instalada. No asumir que el comando tap selecciona una rama de PR.

Competencias relacionadas agrupadas, verificadas contra el upstream `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video. huggingface-hub y llama-cpp están en el catálogo opcional y pueden requerir instalación. ocr-and-documents y pc-hardware-benchmark no estaban en esa instantánea y no son dependencias. Las herramientas de sesión y los backends de documentos y navegador dependen de la configuración local.

## Acceso a fuentes de datos

- Las consultas básicas de OpenAlex pueden ejecutarse de forma anónima con un presupuesto diario menor. Los documentos vigentes al 2026-09-06 indican 0,10 USD/día anónimo y 1 USD/día con clave API gratuita, más un tope de 100 peticiones/segundo. Los costes varían según el tipo de consulta; no es acceso ilimitado. Guardar una clave opcional en `OPENALEX_API_KEY`. Usar `per_page` (máximo 100) y paginación por cursor.
- Crossref ofrece acceso público a metadatos con limitación de velocidad. Las relaciones de actualización y las señales de Retraction Watch exigen comprobaciones de DOI y dirección; la ausencia de registros no prueba que un artículo no esté afectado.
- Unpaywall exige un correo de contacto real en `UNPAYWALL_EMAIL`. La ausencia de ubicación no prueba que no exista copia en acceso abierto.
- arXiv, Europe PMC, PubMed E-utilities y DOAJ son fuentes complementarias con sus propias políticas. No todas se ejercitan en las pruebas por defecto. Semantic Scholar tiene límites anónimos compartidos y límites de clave asignados por separado; el acceso no garantiza disponibilidad del contexto de citas.
- Scite, Dimensions, Scopus, Web of Science y los productos de detección de IA son servicios externos opcionales. Comprobar los derechos y cupos actuales de cuenta y API antes de usarlos; no se promete un nivel gratuito universal ni precios fijos.

Véanse [la autenticación de OpenAlex](https://help.openalex.org/api/authentication/), [los presupuestos y costes de consulta](https://help.openalex.org/api/llm-quick-reference/) y [los filtros de actualización de Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Validación

Usar un entorno Python dedicado. Las bibliotecas de ejecución son específicas de cada tarea y no se garantiza su instalación en Hermes. Las dependencias de QA son más amplias para que todos los ejemplos marcados se ejecuten:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA valida metadatos, referencias, patrones de rutas personales y secretos conocidos, sintaxis Python y vallas ejecutables marcadas. Cada ejemplo smoke se ejecuta sin cambios en un subproceso nuevo. Los ejemplos de trazado aceptan `PLOT_DIR` (por defecto `~/plots`, expandido explícitamente); las pruebas usan un directorio temporal. Las vallas Python sin clasificar se rechazan; los bloques `fragment:` se comprueban sintácticamente pero exigen entradas con nombre y no se ejecutan solos. Los bloques `external-test:` solo se ejecutan mediante el comando externo manual. Devuelve 0 en comprobaciones configuradas superadas, 1 en fallos de código/esquema/identidad y 2 en indisponibilidad de transporte/autenticación/cupo; los servicios opcionales sin configurar permanecen SKIP.

Las pruebas de autoría de Hermes fijadas se reutilizan sin cambiar sus reglas por competencia. Las comprobaciones poblacionales de la distribución completa del upstream no se aplican a este tap; nuestro arnés comprueba trece competencias y resuelve referencias contra el catálogo agrupado y opcional fijado. Esto no es una prueba completa de instalación de Hermes. La CI usa la red solo para instalar dependencias; las pruebas PR ordinarias no llaman a API académicas.

La CI ejecuta la suite QA completa mediante GitHub Actions en Linux x86_64 (Python 3.10-3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 Preview-Canary (ubuntu-26.04 y ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest) y macOS Intel (macos-15-intel) en todas las plataformas y arquitecturas, con 629 pruebas unitarias superadas y validación Canary en vivo de la rama principal de upstream. Un flujo de integración tap separado se ejecuta en las subidas a main: instala el checkout de Hermes fijado registrado en tests/upstream/provenance.json y ejercita tap add, search, install y list contra este repositorio. Las versiones, comprobaciones y limitaciones exactas constan en [la auditoría](docs/audit-20260906.md).

tools/longtail/ aloja el generador determinista de escenarios extremos de cola larga: 4096 combinaciones candidatas con semilla SHA256 sobre los ejes de factores desacoplados, selección voraz de cobertura e informe de cobertura generado en generated-scenarios.json. Es la capa de entrada para someter las competencias a pruebas de estrés; la expansión semántica es una fase independiente.

scripts/scfabric/ es el tejido de computación científica: sonda de hardware, catálogo de backends con filtros de tipo de dato, cinco perfiles de carga de trabajo, banco de pruebas emparejado con verificación de paridad y ComputeReceipt. Las primeras mediciones se encuentran en [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md); la regla general es CPU por defecto, y acelerador solo con ComputeReceipt.

## Documentos de investigación y planificación

- [Atlas de puntos de fricción v0 (inglés)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md): puntos de fricción del ciclo de vida del trabajo académico, con estado de verificación de fuentes para las afirmaciones cuantitativas.
- [Plan de investigación v0 (inglés)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md): modelo Research Object, áreas de competencias fundamentales, direcciones candidatas y la matriz de descomposición factorial de la primera fase.
