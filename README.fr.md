# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

Ensemble déterministe d'outils de gestion et de vérification de l'état de recherche académique pour les flux de travail pilotés par agents, indépendant de tout environnement d'exécution particulier. Par le biais d'une intégration déterministe des artefacts de recherche et d'un serveur universel Model Context Protocol (MCP), il relie l'identification et la traçabilité des objets de recherche, les traces de vérification et éléments probants empiriques, les liens entre affirmations et éléments de preuve, ainsi qu'un journal des décisions de recherche et essais infructueux en ajout seul. 14 compétences académiques spécialisées produisent et consomment cet état de recherche vérifié, avec une prise en charge native de Claude Code, Cursor, Codex, Gemini CLI et Hermes Agent. Le périmètre de validation et les limites des services externes sont consignés dans [l'audit](docs/project-lineage-audit-20260920.md).

Auteur : Junfu Shi (SJF, xngg1021), Hermes Agent. Offre actuelle : [Source Lineage License 1.0](LICENSE).

## Démarrage rapide

Exécutez la version 2.1.0 avec [uv](https://docs.astral.sh/uv/getting-started/installation/) :

```bash
uvx academic-research-kernel@2.1.0 mcp
```

La [version 2.1.0](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0) consigne les empreintes de distribution et l'état de publication. Le fichier wheel de la version peut également être exécuté localement via `uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`. Python 3.10 à 3.14 est pris en charge ; `uvx --python 3.12` sélectionne explicitement un interpréteur compatible. Les 12 outils déterministes, y compris les calculs statistiques, sont inclus dans l'installation de base.

## Vérifier l'installation

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

Le diagnostic hors ligne vérifie les dépendances, les schémas et les 12 définitions d'outils. Les services externes facultatifs peuvent rester non configurés. Utilisez `doctor --json` pour obtenir une sortie lisible par machine.

## Installation du paquet

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Vous pouvez également installer le paquet avec `pipx install academic-research-kernel==2.1.0` ou `python -m pip install academic-research-kernel==2.1.0` dans un environnement virtuel pris en charge. `[full]` ajoute les bibliothèques nécessaires aux exemples étendus de calcul scientifique ; `[qa]` ajoute les outils de validation du dépôt, y compris l'analyseur PDF. `[research]` ajoute `pypdf==6.19.0` et `fonttools==4.65.0` afin d'assurer un décodage cohérent des polices PDF sur les installations neuves (tous deux compatibles avec Python 3.10). La lecture de fichiers HTML/XML structurés et de documents DOCX/XLSX bornés repose sur la bibliothèque standard. Les backends GPU et les services payants restent facultatifs.

## Hermes

Assurez-vous que `uv` figure dans le PATH du processus Hermes, puis installez et activez explicitement l'extension portable :

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

L'identifiant existant `academic-skills` est conservé et regroupe désormais 14 compétences, dont `paper-research`. Le fichier `mcp.json` de l'extension appelle `uv run --frozen --no-dev --no-editable` avec Python 3.12 et le fichier `uv.lock` du dépôt ; son environnement d'exécution est isolé sous `${PLUGIN_DATA}/runtime`. Il installe ses dépendances lors du premier lancement sans emprunter les paquets Python de Hermes ni ceux du système ; un accès réseau est requis au premier démarrage pour récupérer les paquets ou l'interpréteur manquants. L'installation classique par tap de compétences seules demeure prise en charge (voir la section sur l'intégration et l'utilisation portable ci-dessous).

## Exécution depuis les sources

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

Consultez le guide de [distribution et publication](docs/distribution-release.md) pour la classification des dépendances, la reproduction, l'identité des versions, les jalons de publication et le périmètre de validation.

## Licence

L'instantané contenant le présent avis applique la **Source Lineage License 1.0** au matériel couvert et aux droits identifiés dans [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md). Le premier commit SLL et son arbre, ainsi que le commit ultérieur d'enregistrement de frontière, sont distingués dans [LICENSE-HISTORY.md](LICENSE-HISTORY.md) et [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md). Les instantanés postérieurs à cette transition enregistrée qui conservent le présent avis portent la même offre.

Les instantanés historiques jusqu'à `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` étaient distribués sous licence MIT, soumis aux conditions applicables à ces copies. Les destinataires conservent des droits MIT valides et n'ont pas à migrer vers SLL. L'[ancien texte MIT du projet](LICENSES/MIT-pre-SLL.txt) est préservé ; [tests/upstream/LICENSE](tests/upstream/LICENSE) et sa provenance tierce restent inchangés. La nouvelle offre racine n'efface pas ces droits.

SLL autorise largement l'utilisation, l'étude, la modification, l'usage commercial, la distribution et les ajouts propriétaires, sous réserve des conditions de licence, d'avis et de lignage applicables. Elle n'est pas copyleft et n'exige aucune divulgation du code source. Un service réseau pur sans fourniture de copies ne déclenche pas à lui seul la condition d'avis de lignage du service cœur. Aucune concession expresse de brevet. Le matériel tiers demeure soumis à ses propres conditions. Le texte anglais original de la [LICENSE](LICENSE) prévaut sur ce résumé informatif ; `LicenseRef-Source-Lineage-1.0` est une référence locale, non une affectation SPDX, et aucune approbation OSI n'est revendiquée. L'[admission des contributions](CONTRIBUTING.md) est distincte des permissions de licence en aval.

## Compétences

| Compétence | Version | Fonction |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Vérifier l'identité et les comptes de citations par source ; examiner les signaux de mise à jour et de rétractation ; localiser le texte en accès libre et vérifier l'identité des PDF |
| `skills/literature-analysis` | 1.3.0 | Douze flux : similarité thématique, chevauchement local, contre-preuves, profils d'auteurs, revue simulée, vérification des sophismes, matrice de revue, revues candidates, BibTeX, lecture bilingue, dépistage des lacunes, reproduction |
| `skills/academic-writing` | 1.1.1 | Révision éditoriale, normes de citation (ISO 690, APA, MLA, Chicago, IEEE, AMA et profils régionaux), consignes aux auteurs, services facultatifs de détection, dossiers de soumission et exigences institutionnelles |
| `skills/math-computation` | 1.2.1 | Routage domaine/tâche existant avec exemples numériques et statistiques corrigés ; quatre fichiers de référence par domaine |
| `skills/quantitative-paper-audit` | 1.1.0 | Recalculer les statistiques rapportées (taille d'effet, valeurs p, intervalles de confiance, OR/RR, puissance atteinte) et détecter les incohérences numériques |
| `skills/research-reproducibility` | 1.0.1 | Pipeline d'audit de reproduction en quatorze étapes avec listes de contrôle structurées, cinq niveaux de faits et enregistrements d'audit vérifiables |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Journaux de recherche PRISMA, journal de sélection de la littérature, conversion des tailles d'effet, hétérogénéité, regroupement à effets fixes/aléatoires, diagnostics de sensibilité et de biais de publication |
| `skills/literature-watch` | 1.1.0 | Plan hebdomadaire : surveiller les thèmes, auteurs et œuvres citant des DOI sur OpenAlex et Crossref ; dédupliquer et ne signaler que les nouveautés |
| `skills/retraction-watch` | 1.1.0 | Plan hebdomadaire : revérifier une liste de DOI contre OpenAlex `is_retracted` et les enregistrements de mise à jour Crossref (signaux `update-to`) ; ne signaler que les changements d'état |
| `skills/research-object-identity` | 1.1.0 | Identification déterministe des ressources de recherche et provenance / traçabilité : normalisation des identifiants, vérification à 5 états, graphe de dérivation adressé par le contenu, validation DAG causale et traçage hors ligne en moins de 100 ms |
| `skills/claim-evidence-graph` | 1.0.0 | Liens entre affirmations et éléments de preuve : connexion déterministe des affirmations scientifiques, des traces de vérification et de la provenance computationnelle |
| `skills/decision-ledger` | 1.0.0 | Journal des décisions de recherche et essais infructueux : journal déterministe en ajout seul des décisions de recherche, essais infructueux (résultats négatifs), état de la piste / raison de l'abandon de cette piste et révisions de conclusions |
| `skills/paper-research` | 1.0.0 | Lecture d'articles et de données supplémentaires via DOI, URL ou fichiers locaux avec validation des champs candidats, contrôles statistiques, état de recherche persistant, rapports en chinois liés aux sources et comparaison de deux articles |
| `skills/cross-review-five` | 2.0.0 | Orchestration dynamique de panel d'évaluation multi-modèles et sous-agents (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini, etc.) : pipeline v2 Sparse Deliberation avec affectation hongroise de Kuhn-Munkres, regroupement d'affirmations, interpellation anonyme ciblée et niveaux de gravité P0–P3 |

Les quatorze compétences comprennent 22 fichiers de référence Markdown, chargés uniquement à la demande.

## Normes académiques et référentiel multi-profils

Les styles de citation, les critères de rapport et les contrats de métadonnées dépendent de la revue cible, de l'organisme de financement, de la discipline et de la juridiction. Le dépôt établit **ISO 690:2021** (références bibliographiques), **ISO 5127:2017** (vocabulaire de l'information et de la documentation) et **W3C PROV** (modèle de données de provenance) comme bases internationales, complétées par des profils régionaux (par ex. NF ISO 690 en France, GB/T 7714-2025 en Chine continentale, UNE-ISO 690:2024 en Espagne, DIN ISO 690:2021 en Allemagne) et des normes disciplinaires (APA 7e, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Les exigences de l'organe de publication cible prévalent toujours sur les profils par défaut. Voir [Architecture des normes académiques](docs/standards/README.md) et [Guide de terminologie naturelle](docs/terminology/README.md).

La version 2.1.0 valide la cohérence des DOI et identifiants externes, l'exclusivité mutuelle des indicateurs de verdict quantitatif ainsi que le contrat de points à vérifier partagé entre le noyau et les traces de vérification. L'intégrité du cache est reconstruite à partir des enveloppes sources conservées et des liaisons normalisées, indépendamment des listes de mutations de la trace ; la suppression simultanée d'un enregistrement et de sa déclaration de cache ne peut produire aucune relecture acceptée. Voir [la clôture des quatre points bloquants](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Intégration et utilisation portable

### 1. Agent Plugins v1 universel et Model Context Protocol (MCP)
Ce dépôt est conforme à la spécification neutre **Agent Plugins v1** (`plugin.json`) et expose les outils essentiels de vérification académique et de recalcul statistique via un **serveur MCP** stdio (`mcp.json` / `scripts/mcp_server.py`). Compatible avec Claude Code, Cursor, Gemini CLI et tout framework moderne d'agents. (Remarque : bien que l'identité du dépôt soit `academic-research-kernel`, le nom du manifeste d'extension `academic-skills` et les alias de configuration MCP restent stables par souci de rétrocompatibilité.)

```bash
# Ajouter en tant que serveur stdio MCP dans votre environnement d'agents
uvx academic-research-kernel mcp
```

### 2. Installation native dans Hermes
Depuis une installation Hermes :

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Installez les autres compétences en substituant leur nom de répertoire dans l'identifiant complet. Un tap normal lit la branche par défaut, de sorte qu'un tap neuf installe l'ensemble ci-dessus. Pour inspecter une branche de travail avant fusion, extrayez cette branche localement et suivez les instructions d'installation en dossier local de la version Hermes installée. Ne supposez pas que la commande tap sélectionne automatiquement une branche de pull request.

Compétences liées groupées vérifiées à l'amont `245e48008fa814b3251f50755eb656bd9fb86cb1` : arxiv, grounded-citations, docx, pdf, manim-video. huggingface-hub et llama-cpp figurent au catalogue optionnel et peuvent exiger une installation séparée. ocr-and-documents et pc-hardware-benchmark n'étaient pas présents dans cet instantané et ne sont pas des dépendances. Les outils de session et les backends documentaires ou navigateur dépendent de la configuration locale.

## Accès aux sources de données

- Les requêtes OpenAlex de base peuvent s'exécuter anonymement avec un budget quotidien réduit. Les documents en vigueur au 2026-09-06 précisent 0,10 USD/jour en anonyme et 1 USD/jour avec une clé API gratuite, plus un plafond de 100 requêtes/seconde. Les coûts varient selon le type de requête ; ce n'est pas un accès illimité. Rangez une clé optionnelle dans `OPENALEX_API_KEY`. Utilisez `per_page` (maximum 100) et la pagination par curseur.
- Crossref offre un accès public aux métadonnées avec limitation de débit. Les relations de mise à jour et les signaux Retraction Watch exigent des vérifications de DOI et de direction ; l'absence d'enregistrement ne prouve pas qu'un article est épargné.
- Unpaywall exige une adresse de contact réelle dans `UNPAYWALL_EMAIL`. L'absence de localisation ne prouve pas l'absence de copie en accès libre.
- arXiv, Europe PMC, PubMed E-utilities et DOAJ sont des sources complémentaires avec leurs propres règles. Les tests par défaut ne les sollicitent pas toutes. Semantic Scholar a des limites anonymes partagées et des limites de clé attribuées séparément ; l'accès ne garantit pas la disponibilité du contexte de citation.
- Scite, Dimensions, Scopus, Web of Science et les produits de détection d'IA sont des services externes optionnels. Vérifiez les droits et quotas actuels du compte et de l'API avant usage ; aucun palier gratuit universel ni prix fixe n'est promis.

Voir [l'authentification OpenAlex](https://help.openalex.org/api/authentication/), [les budgets et coûts de requête](https://help.openalex.org/api/llm-quick-reference/) et [les filtres de mise à jour Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Intégration déterministe et interface publique du noyau

La version 2.1.0 fournit `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 adaptateurs (les 14 compétences plus un repli opaque) et 12 outils MCP stdio sans état. Les traces d'intégration acceptées lient chaque mutation sémantique conservée par type, identité et empreinte SHA-256 canonique : objets de recherche, enregistrements de liens entre affirmations et éléments de preuve, entrées du journal des décisions de recherche et essais infructueux, points à vérifier, traces de vérification physiques et enregistrements d'artefacts. La relecture du cache vérifie ces engagements indépendamment des empreintes d'instantanés de transport. Les journaux vides sont valides ; les lots atomiques en échec ne laissent aucun état partiel.

L'autorisation de lecture du contenu de provenance est explicite et hors bande. Les appelants Python de confiance transmettent `LineageVerificationContext` lors de la relecture de traces ou d'instantanés sérialisés ; les appelants MCP peuvent fournir un flux d'octets borné, mais jamais une racine du système de fichiers hôte. Le budget de contenu par défaut est de 10 Mio ; un hôte de confiance peut autoriser explicitement des artefacts plus volumineux selon la même politique entre producteur et vérificateur. Sans autorisation d'accès au contenu, une affirmation `fully_verified` ne peut pas être reproduite de manière indépendante et renvoie un résultat de vérification invalide structuré. Le texte non structuré reste opaque, les divergences d'analyse demeurent visibles et les chercheurs conservent la maîtrise des validations, de l'abandon ou de la réouverture de pistes, du routage et des jugements scientifiques.

Consultez [l'architecture du noyau](docs/kernel-architecture.md) pour les contrats et règles de compatibilité. Les jalons de distribution et de publication sont consignés dans [le guide de publication](docs/distribution-release.md). Les fichiers README en anglais et en chinois simplifié sont à jour ; l'état des autres traductions est détaillé dans [le manifeste](docs/i18n/manifest.json). L'identité du candidat final, la CI sur HEAD exact, les revues cumulées et les preuves de fusion sont consignées dans [le journal de clôture](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Validation

Utilisez un environnement Python dédié. Les bibliothèques d'exécution sont propres à chaque tâche et ne sont pas garanties installées dans Hermes. Les dépendances QA sont plus larges afin que tous les exemples marqués s'exécutent :

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

QA valide les métadonnées, les références, les motifs de chemins personnels et de secrets connus, la syntaxe Python et les blocs de code exécutables marqués. Chaque exemple smoke s'exécute tel quel dans un sous-processus neuf. Les exemples de tracé acceptent `PLOT_DIR` (par défaut `~/plots`, étendu explicitement) ; les tests utilisent un répertoire temporaire. Les blocs Python non classifiés sont refusés ; les blocs `fragment:` sont vérifiés syntaxiquement mais exigent des entrées nommées et ne s'exécutent pas seuls. Les blocs `external-test:` ne s'exécutent que via la commande externe manuelle. Elle renvoie 0 pour les contrôles configurés réussis, 1 pour un échec de code/schéma/identité, et 2 pour une indisponibilité de transport/authentification/quota ; les services optionnels non configurés restent SKIP.

Les tests d'autorat Hermes épinglés sont réutilisés sans modifier leurs règles par compétence. Les contrôles de population sur la distribution complète amont ne s'appliquent pas à ce tap ; notre banc de test vérifie quatorze compétences et résout les références contre le catalogue groupé et optionnel épinglé. Ce n'est pas un test d'installation Hermes complet. La CI n'utilise le réseau que pour installer les dépendances ; les tests courants n'appellent pas d'API académiques.

La CI exécute la suite QA complète sur Linux x86_64 (Python 3.10–3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 Preview-Canary (ubuntu-26.04 & ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest) et macOS Intel (macos-15-intel), avec validation Canary continue de la branche amont. Le candidat de référence historique a réussi 1165 tests locaux ; les résultats de correction actuels et les limites de couverture sont consignés dans [le rapport de correction](docs/maintenance/correctness-repair-20261008.md), les preuves distantes identifiant séparément le HEAD testé. Un flux d'intégration tap séparé s'exécute lors des poussées sur main : il installe l'extraction Hermes épinglée consignée dans tests/upstream/provenance.json et exerce tap add, search, install et list contre ce dépôt. Les versions, contrôles et limites exacts figurent dans [l'audit](docs/project-lineage-audit-20260920.md).

[tools/longtail/](tools/longtail/README.md) héberge le générateur déterministe de facteurs de longue traîne : 4096 candidats initialisés par SHA256, 30 scénarios sélectionnés et un rapport de couverture de vérification calculé par machine. Le modèle v3 comptabilise séparément les familles de capacités (E01), les 14 compétences effectives du dépôt (E02) et les objectifs de tâche (E03). Chaque scénario possède une compétence principale, un objectif de tâche pris en charge et des capacités compatibles ; chaque compétence doit apparaître au moins deux fois sous deux objectifs distincts, y compris son objectif principal déclaré. Toute dérive des répertoires de compétences fait échouer la validation. L'expansion sémantique (chaînes de tâches, oracles et injection d'événements exécutés) demeure une étape distincte ; la couverture des facteurs ne prouve pas la couverture d'exécution des flux de travail.

scripts/scfabric/ constitue la couche d'exécution de la suite d'outils de calcul scientifique et de statistiques : sonde matérielle, catalogue de backends avec contrôles dtype, cinq profils de charge, banc d'essai apparié avec admission par parité et ComputeReceipt. Les premières mesures sur cette machine figurent dans [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md) ; la règle générale est d'utiliser le CPU par défaut, et l'accélérateur uniquement avec une trace de vérification ComputeReceipt.

## Étudier un article avec un Agent local

Installez `academic-research-kernel[research]==2.1.0` et exportez le flux de travail fourni avec le paquet :

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Demandez à Work ou à un Agent local compatible de lire ce fichier `SKILL.md` exporté, puis formulez la requête suivante :
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Fournissez uniquement le DOI, le lien public ou l'archive locale. Pour deux articles, demandez-lui de comparer les données, les méthodes, les conditions d'évaluation et les résultats en expliquant ce qui est directement comparable. L'Agent enchaîne dans la même tâche la lecture du texte original, la validation des candidats, les calculs, l'intégration, la génération du rapport et la relecture indépendante des sources. La surface MCP existante conserve ses 12 outils ; la nouvelle orchestration réside dans l'interface CLI et la compétence portable.

Les étapes effectives du programme sont les suivantes :

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` récupère et analyse le matériel pour produire un manifeste, les empreintes des sources et les segments localisés. `finish` valide l'extraction produite par l'Agent, recalcule les valeurs t/p, tailles d'effet à deux groupes et effectifs/pourcentages éligibles à l'aide des outils statistiques existants, puis enregistre l'état du noyau ainsi que les rapports Markdown/HTML en chinois. `compare` valide l'évaluation explicite des conditions comparables fournie par l'Agent. Ces commandes n'embarquent aucun modèle Work résident : la lecture sémantique est effectuée par l'Agent courant en suivant [paper-research](skills/paper-research/SKILL.md). Les fichiers originaux et instantanés d'extraction sauvegardés permettent une relecture hors ligne déterministe. L'acquisition réseau et une nouvelle lecture sémantique restent des opérations identifiées séparément.

## 2.0.1 Vérification de justesse et de distribution

Depuis la version 2.0.1, l'outil public `academic_recompute_statistics` expose les valeurs p des tests t ainsi que le d de Cohen et le g de Hedges à deux groupes, tandis que les intervalles de confiance (CI) et les rapports OR/RR restent des fonctions Python de plus bas niveau. Fournissez `p_value_literal` (par exemple `"1.0e-5"`) ou `p_value_decimals` lorsque la précision rapportée importe. Les chaînes littérales préservent les zéros finaux ; les entrées numériques ne conservent que leur représentation numérique. Des sources de précision contradictoires échouent explicitement. Les comparaisons d'arrondi au plus proche (round-half-up) incluent la borne inférieure et excluent la borne supérieure. Une divergence numérique ordinaire constitue un résultat scientifique valide ; seuls les calculs invalides ou partiellement en échec activent `isError`.

Les contrôles de rétractation enregistrent l'observation courante (`True` / `False` / `unknown`) séparément de la dernière valeur connue. Une courte réservation préalable ordonne les observations portant sur un même DOI et préserve les mises à jour des autres DOI. Les observations courantes et les confirmations historiques disposent de versions distinctes : une confirmation tardive peut enrichir l'historique conservé tandis qu'une observation `unknown` plus récente demeure explicitement non vérifiée pour le contrôle en cours. Les fixtures HTTP des chaînes de régression sont étiquetées comme données de test.

Le serveur MCP répond à `ping`, reste silencieux face aux notifications valides (y compris `notifications/cancelled`) et maintient la session stdio active après une entrée invalide. L'implémentation synchrone n'annonce pas d'annulation préemptive. Le traitement des messages respecte le [contrat de messages MCP](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) et la [spécification ping](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Construisez et vérifiez les distributions de cette copie de travail dans un environnement isolé :

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` extrait l'archive sdist candidate telle quelle hors du dépôt, définit `ARK_REPO` et `ARK_SDIST` sur ce candidat, puis exécute ses tests, la QA statique, les blocs de code exécutables et la vérification i18n. Les installations wheel et sdist utilisent chacune un environnement neuf ; `uvx` utilise le fichier wheel local avec un cache indépendant. Le rapport consigne les empreintes des artefacts et les chemins d'importation installés. Les contrôles Hermes légers planifiés (version épinglée et dernière version) rapportent le SHA testé séparément. Les fichiers JSON de contrat externe et les résumés de tâches utilisent `healthy`, `degraded` et `failed` ; les sondes ignorées restent explicites.

## Documents de recherche et de planification

Ces deux documents sont des références de planification exploratoire et non une feuille de route contraignante. Leurs numéros de direction sont recalculés à partir du regroupement enregistré dans docs/direction-primitive-mapping.json.

- [Atlas des points de friction v0 (anglais)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md) : points de friction du cycle de vie du travail académique, avec état de vérification des sources pour les affirmations quantitatives.
- [Plan de recherche v0 (anglais)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md) : modèle Research Object, domaines de compétences fondamentales, directions candidates et matrice de décomposition factorielle de la première phase.
