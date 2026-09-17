# hermes-academic-skills

English · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · Français · [Español](README.es.md)

Onze compétences académiques en chinois pour Hermes Agent : vérification des sources, analyse documentaire, rédaction académique, calcul numérique, audit quantitatif d'articles, audits de reproductibilité, revues systématiques et méta-analyses, identité et lignage des objets de recherche, orchestration de revues inter-modèles, plus deux automatisations de veille hebdomadaire. Le dépôt inclut des contrôles d'exemples exécutables ; le périmètre de validation et les limites des services externes sont consignés dans [l'audit](docs/audit-20260906.md).

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
| `skills/academic-writing` | 1.1.1 | Édition, conseils de citation (APA, MLA, Chicago, IEEE, AMA, GB/T), instructions des revues, services de détection optionnels, matériaux de soumission, exigences académiques chinoises |
| `skills/math-computation` | 1.2.1 | Routage domaine/tâche existant avec exemples numériques et statistiques corrigés ; quatre fichiers de référence par domaine |
| `skills/quantitative-paper-audit` | 1.1.0 | Recalculer les statistiques rapportées (taille d'effet, valeurs p, intervalles de confiance, OR/RR, puissance atteinte) et détecter les incohérences numériques |
| `skills/research-reproducibility` | 1.0.1 | Pipeline d'audit de reproduction en quatorze étapes avec moteur de liste de contrôle structuré, cinq niveaux de faits et reçu à quatre états |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Journaux de recherche PRISMA, registres de sélection, conversion des tailles d'effet, hétérogénéité, regroupement à effets fixes/aléatoires, diagnostics de sensibilité et de biais de publication |
| `skills/literature-watch` | 1.1.0 | Plan hebdomadaire : surveiller les thèmes, auteurs et œuvres citant des DOI sur OpenAlex et Crossref ; dédupliquer et ne signaler que les nouveautés |
| `skills/retraction-watch` | 1.1.0 | Plan hebdomadaire : revérifier une liste de DOI contre OpenAlex is_retracted et les enregistrements de mise à jour Crossref (signaux update-to) ; ne signaler que les changements d'état |
| `skills/research-object-identity` | 1.0.0 | Couche d'identité déterministe des objets de recherche : normalisation des identifiants, verdict à cinq états (sans score de confiance), arêtes de relation et de lignage ; consomme les reçus de preuve |
| `skills/cross-review-five` | 2.0.0 | Panel de revue hétérogène à cinq modèles (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Gemini 3.8 Flash, Gemini 3.1 Pro) : pipeline Sparse Deliberation v2 en quatre étapes (plan indépendant, regroupement/fusion au niveau des affirmations, contestation anonyme ciblée et réconciliation avec registre non résolu) |

Les onze compétences comprennent 21 fichiers de référence Markdown, chargés uniquement à la demande. GB/T 7714-2025 est en vigueur ; la référence d'écriture distingue sa date d'entrée en vigueur vérifiée des exemples explicitement étiquetés de 2015. La conformité complète à l'édition 2025 exige le modèle ou le texte standard de l'institution cible.

## Installation dans Hermes

La découverte de tap amont actuelle inspecte les sous-répertoires immédiats de `skills/`. Chaque compétence vit donc directement sous cette racine. Depuis une installation Hermes :

```bash
hermes skills tap add xngg1021/hermes-academic-skills
hermes skills search academic-source-verification
hermes skills install xngg1021/hermes-academic-skills/skills/academic-source-verification
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

Les tests d'autorat Hermes épinglés sont réutilisés sans modifier leurs règles par compétence. Les contrôles de population sur la distribution complète amont ne s'appliquent pas à ce tap ; notre harnais vérifie onze compétences et résout les références contre le catalogue groupé/optionnel épinglé. Ce n'est pas un test d'installation Hermes complet. La CI n'utilise le réseau que pour installer les dépendances ; les tests PR ordinaires n'appellent pas d'API académiques.

La CI exécute la suite QA complète via GitHub Actions sur Ubuntu (Python 3.12 et 3.13), Windows et macOS. Un flux d'intégration tap séparé s'exécute lors des poussées sur main : il installe l'extraction Hermes épinglée consignée dans tests/upstream/provenance.json et exerce tap add, search, install et list contre ce dépôt. Une session Hermes neuve et chaque combinaison de versions de dépendances ne sont pas revendiquées. Les versions, contrôles et limites exacts figurent dans [l'audit](docs/audit-20260906.md).

## Documents de recherche et de planification

- [Atlas des points de friction v0 (anglais)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md) : points de friction du cycle de vie du travail académique, avec état de vérification des sources pour les affirmations quantitatives.
- [Plan de recherche v0 (anglais)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md) : quatorze primitives architecturales, le modèle Research Object, quatre plans, directions candidates et la matrice de décomposition factorielle de la première phase.
