# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

Noyau de recherche académique neutre vis-à-vis des environnements et suite de délibération multi-agents. Il fournit 13 compétences académiques et outils de vérification avec des points d'entrée portables Agent Plugins v1 et MCP, ainsi qu'une intégration native pour Hermes Agent, Claude Code, Cursor et les sous-agents CLI personnalisés. Ils couvrent la vérification des sources, l'analyse documentaire, la rédaction académique, le calcul numérique, l'audit quantitatif d'articles, les audits de reproductibilité, les revues systématiques et méta-analyses, l'identité et le lignage des objets de recherche, l'orchestration de revues inter-modèles, plus deux automatisations de veille hebdomadaire. Le dépôt inclut des contrôles d'exemples exécutables ; le périmètre de validation et les limites des services externes sont consignés dans [l'audit](docs/project-lineage-audit-20260920.md).

Auteur : Junfu Shi (SJF, xngg1021), Hermes Agent. Offre actuelle : [Source Lineage License 1.0](LICENSE).

## Licence

L'instantané contenant le présent avis applique la **Source Lineage License 1.0** au matériel couvert et aux droits identifiés dans [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md). Le premier commit SLL et son arbre, ainsi que le commit ultérieur d'enregistrement de frontière, sont distingués dans [LICENSE-HISTORY.md](LICENSE-HISTORY.md) et [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md). Les instantanés postérieurs à cette transition enregistrée qui conservent le présent avis portent la même offre.

Les instantanés historiques jusqu'à `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` étaient distribués sous licence MIT, soumis aux conditions applicables à ces copies. Les destinataires conservent des droits MIT valides et n'ont pas à migrer vers SLL. L'[ancien texte MIT du projet](LICENSES/MIT-pre-SLL.txt) est préservé ; [tests/upstream/LICENSE](tests/upstream/LICENSE) et sa provenance tierce restent inchangés. La nouvelle offre racine n'efface pas ces droits.

SLL autorise largement l'utilisation, l'étude, la modification, l'usage commercial, la distribution et les ajouts propriétaires, sous réserve des conditions de licence, d'avis et de lignage applicables. Elle n'est pas copyleft et n'exige aucune divulgation du code source. Un service réseau pur sans fourniture de copies ne déclenche pas à lui seul la condition d'avis de lignage du service cœur. Aucune concession expresse de brevet. Le matériel tiers demeure soumis à ses propres conditions. Le texte anglais original de la [LICENSE](LICENSE) prévaut sur ce résumé informatif ; `LicenseRef-Source-Lineage-1.0` est une référence locale, non une affectation SPDX, et aucune approbation OSI n'est revendiquée. L'[admission des contributions](CONTRIBUTING.md) est distincte des permissions de licence en aval.

## Compétences

| Compétence | Version | Fonction |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Vérifier l'identité et les comptes de citations par source ; examiner les signaux de mise à jour et de rétractation ; localiser le texte en accès libre et vérifier l'identité des PDF |
| `skills/literature-analysis` | 1.3.0 | Douze flux : similarité thématique, chevauchement local, contre-preuves, profils d'auteurs, revue simulée, vérification des sophismes, matrice de revue, revues candidates, BibTeX, lecture bilingue, dépistage des lacunes, reproduction |
| `skills/academic-writing` | 1.1.1 | Révision éditoriale, normes de citation (ISO 690, APA, MLA, Chicago, IEEE, AMA et profils régionaux), consignes aux auteurs, services d'évaluation, dossiers de soumission et exigences institutionnelles |
| `skills/math-computation` | 1.2.1 | Routage domaine/tâche existant avec exemples numériques et statistiques corrigés ; quatre fichiers de référence par domaine |
| `skills/quantitative-paper-audit` | 1.1.0 | Recalculer les statistiques rapportées (taille d'effet, valeurs p, intervalles de confiance, OR/RR, puissance atteinte) et détecter les incohérences numériques |
| `skills/research-reproducibility` | 1.0.1 | Pipeline d'audit de reproduction en quatorze étapes avec listes de contrôle structurées, cinq niveaux de faits et enregistrements d'audit vérifiables |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Journaux de recherche PRISMA, journaux de sélection documentaire, conversion des tailles d'effet, hétérogénéité, regroupement à effets fixes/aléatoires, diagnostics de sensibilité et de biais de publication |
| `skills/literature-watch` | 1.1.0 | Plan hebdomadaire : surveiller les thèmes, auteurs et œuvres citant des DOI sur OpenAlex et Crossref ; dédupliquer et ne signaler que les nouveautés |
| `skills/retraction-watch` | 1.1.0 | Plan hebdomadaire : revérifier une liste de DOI contre OpenAlex is_retracted et les enregistrements de mise à jour Crossref (signaux update-to) ; ne signaler que les changements d'état |
| `skills/research-object-identity` | 1.1.0 | Identification des ressources de recherche et traçabilité déterministe : normalisation des identifiants, verdict à 5 états, graphe de dérivation adressé par le contenu, validation DAG causale et traçage hors ligne |
| `skills/claim-evidence-graph` | 1.0.0 | Liens déterministes entre affirmations et éléments de preuve : connexion des affirmations scientifiques, preuves empiriques et traçabilité |
| `skills/decision-ledger` | 1.0.0 | Journal des décisions de recherche et essais infructueux : journal déterministe en ajout seul des décisions, résultats négatifs, raisons d'abandon de pistes et révisions de conclusions |
| `skills/cross-review-five` | 2.0.0 | Panel de révision multi-modèles et sous-agents dynamique (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini, etc.) : pipeline v2 Sparse Deliberation en 4 phases avec affectation hongroise de Kuhn-Munkres et niveaux de gravité P0-P3 |

Les treize compétences comprennent 21 fichiers de référence Markdown, chargés uniquement à la demande.

## Normes académiques et référentiel multi-profils

Les styles de citation, les critères de rapport et les métadonnées dépendent de la revue cible, de l'organisme de financement, de la discipline et de la juridiction. Le dépôt établit **ISO 690:2021** (références et citations), **ISO 5127:2017** (vocabulaire de l'information et de la documentation) et **W3C PROV** (modèle de données de provenance) comme bases internationales, complétées par des profils régionaux (par ex. NF ISO 690 en France, GB/T 7714-2025 en Chine continentale, UNE-ISO 690 en Espagne) et des normes disciplinaires (APA 7e, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Les exigences de l'institution cible prévalent toujours. Voir [Architecture des normes académiques](docs/standards/README.md) et [Guide de terminologie naturelle](docs/terminology/README.md).

## Intégration & Installation

### 1. Agent Plugins v1 & Serveur MCP
Ce dépôt est conforme à la spécification neutre **Agent Plugins v1** (`plugin.json`) et expose les outils essentiels de vérification académique et de recalcul statistique via un **serveur MCP** stdio (`mcp.json` / `python scripts/mcp_server.py`). Compatible avec Claude Code, Cursor, Gemini CLI et tout framework moderne d'agents.

```bash
# Ajouter en tant que serveur stdio MCP dans votre environnement
python scripts/mcp_server.py
```

### 2. Installation dans Hermes

La découverte de tap amont actuelle inspecte les sous-répertoires immédiats de `skills/`. Chaque compétence vit donc directement sous cette racine. Depuis une installation Hermes :

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Installer les autres en substituant leur nom de répertoire dans l'identifiant complet. Un tap normal lit la branche par défaut, de sorte qu'un tap frais installe l'ensemble ci-dessus. Pour inspecter une branche de travail avant fusion, extraire cette branche localement et suivre les instructions d'installation en dossier local de la version Hermes installée. Ne pas supposer que la commande tap sélectionne une branche de PR.

Compétences liées groupées vérifiées à l'amont `245e48008fa814b3251f50755eb656bd9fb86cb1` : arxiv, grounded-citations, docx, pdf, manim-video. huggingface-hub et llama-cpp figurent au catalogue optionnel et peuvent exiger une installation. ocr-and-documents et pc-hardware-benchmark n'étaient pas présents dans cet instantané et ne sont pas des dépendances. Les outils de session et les backends documentaires/navigateur dépendent de la configuration locale.

## Accès aux sources de données

- Les requêtes OpenAlex de base peuvent s'exécuter anonymement avec un budget quotidien réduit. Les documents en vigueur au 2026-09-06 précisent 0,10 USD/jour en anonyme et 1 USD/jour avec une clé API gratuite, plus un plafond de 100 requêtes/seconde. Les coûts varient selon le type de requête ; ce n'est pas un accès illimité. Ranger une clé optionnelle dans `OPENALEX_API_KEY`. Utiliser `per_page` (maximum 100) et la pagination par curseur.
- Crossref offre un accès public aux métadonnées avec limitation de débit. Les relations de mise à jour et les signaux Retraction Watch exigent des vérifications de DOI et de direction ; l'absence d'enregistrement ne prouve pas qu'un article est épargné.
- Unpaywall exige une adresse de contact réelle dans `UNPAYWALL_EMAIL`. L'absence de localisation ne prouve pas l'absence de copie en accès libre.
- arXiv, Europe PMC, PubMed E-utilities et DOAJ sont des sources complémentaires avec leurs propres règles. Les tests par défaut ne les sollicitent pas toutes. Semantic Scholar a des limites anonymes partagées et des limites de clé attribuées séparément ; l'accès ne garantit pas la disponibilité du contexte de citation.
- Scite, Dimensions, Scopus, Web of Science et les produits de détection d'IA sont des services externes optionnels. Vérifier les droits et quotas actuels du compte et de l'API avant usage ; aucun palier gratuit universel ni prix fixe n'est promis.

Voir [l'authentification OpenAlex](https://help.openalex.org/api/authentication/), [les budgets et coûts de requête](https://help.openalex.org/api/llm-quick-reference/) et [les filtres de mise à jour Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Validation

Utiliser un environnement Python dédié. Les bibliothèques d'exécution sont propres à chaque tâche et ne sont pas garanties installées dans Hermes. Les dépendances QA sont plus larges afin que tous les exemples marqués s'exécutent :

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA valide les métadonnées, les références, les motifs de chemins personnels et de secrets connus, la syntaxe Python et les clôtures exécutables marquées. Chaque exemple smoke s'exécute tel quel dans un sous-processus neuf. Les exemples de tracé acceptent `PLOT_DIR` (par défaut `~/plots`, étendu explicitement) ; les tests utilisent un répertoire temporaire. Les clôtures Python non classifiées sont refusées ; les blocs `fragment:` sont vérifiés syntaxiquement mais exigent des entrées nommées et ne s'exécutent pas seuls. Les blocs `external-test:` ne s'exécutent que via la commande externe manuelle. Retour : 0 pour les contrôles configurés réussis, 1 pour un échec de code/schéma/identité, 2 pour une indisponibilité de transport/authentification/quota ; les services optionnels non configurés restent SKIP.

Les tests d'autorat Hermes épinglés sont réutilisés sans modifier leurs règles par compétence. Les contrôles de population sur la distribution complète amont ne s'appliquent pas à ce tap ; notre harnais vérifie treize compétences et résout les références contre le catalogue groupé/optionnel épinglé. Ce n'est pas un test d'installation Hermes complet. La CI n'utilise le réseau que pour installer les dépendances ; les tests PR ordinaires n'appellent pas d'API académiques.

La CI exécute la suite QA complète via GitHub Actions sur Linux x86_64 (Python 3.10-3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 Preview-Canary (ubuntu-26.04 et ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest) et macOS Intel (macos-15-intel) sur toutes les plateformes et architectures, avec 713 tests unitaires réussis et une validation Canary continue de la branche principale amont. Un flux d'intégration tap séparé s'exécute lors des poussées sur main : il installe l'extraction Hermes épinglée consignée dans tests/upstream/provenance.json et exerce tap add, search, install et list contre ce dépôt. Les versions, contrôles et limites exacts figurent dans [l'audit](docs/project-lineage-audit-20260920.md).

tools/longtail/ héberge le générateur déterministe de scénarios extrêmes: 4096 combinaisons candidates initialisées par SHA256 sur les axes de facteurs découplés, sélection gloutonne de couverture et rapport calculé par machine dans generated-scenarios.json. Il s'agit de la couche d'entrée pour tester la robustesse des compétences; l'expansion sémantique est une étape séparée.

scripts/scfabric/ constitue la structure de calcul scientifique: sonde matérielle, catalogue de backends avec contrôles dtype, cinq profils de charge, banc d'essai apparié avec vérification de parité et ComputeReceipt. Les mesures figurent dans [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md); la règle générale est le CPU par défaut, et l'accélérateur uniquement avec ComputeReceipt.

## Documents de recherche et de planification

- [Atlas des points de friction v0 (anglais)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md) : points de friction du cycle de vie du travail académique, avec état de vérification des sources pour les affirmations quantitatives.
- [Plan de recherche v0 (anglais)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md) : modèle Research Object, domaines de compétences fondamentales, directions candidates et la matrice de décomposition factorielle de la première phase.
