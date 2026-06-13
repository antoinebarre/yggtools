# SRS — Software Requirements Specification

**Projet :** uvforge  
**Version :** 1.0  
**Date :** 2026-06-12  
**Auteur :** Antoine Barré  
**Statut :** Draft

---

## Table des matières

1. [Introduction](#1-introduction)
2. [Description générale](#2-description-générale)
3. [Exigences fonctionnelles](#3-exigences-fonctionnelles)
4. [Exigences non fonctionnelles](#4-exigences-non-fonctionnelles)
5. [Contraintes système](#5-contraintes-système)
6. [Exigences sur les scripts embarqués](#6-exigences-sur-les-scripts-embarqués)
7. [Exigences de test](#7-exigences-de-test)
8. [Glossaire](#8-glossaire)

---

## 1. Introduction

### 1.1 Objet

Ce document spécifie les exigences logicielles du projet **uvforge**, un outil en ligne de commande qui étend `uv` pour fournir une couche d'organisation, de scripts de qualité et de pipeline CI reproductible pour les packages Python.

### 1.2 Périmètre

uvforge couvre :
- L'initialisation de la structure d'un package Python (`uvforge init`)
- L'audit de conformité d'un projet existant (`uvforge check`)
- La mise à jour des fichiers gérés (`uvforge update`)
- La génération d'un pipeline qualité complet via `Makefile`
- La fourniture de scripts de qualité, métriques, sécurité et publication

uvforge ne couvre pas :
- L'exécution directe des outils qualité (ruff, mypy, pytest…) — ceux-ci sont délégués au `Makefile` et aux scripts
- La gestion des secrets PyPI (responsabilité de l'utilisateur)
- La création de branches git ou la gestion de workflows GitHub/GitLab

### 1.3 Références

- [mkforge](https://github.com/antoinebarre/mkforge) — référence de pipeline
- [uv documentation](https://docs.astral.sh/uv/)
- [PEP 517/518](https://peps.python.org/pep-0517/) — build system

### 1.4 Conventions

- **SHALL** : exigence obligatoire
- **SHOULD** : exigence recommandée
- **MAY** : exigence optionnelle
- Identifiant d'exigence : `REQ-<catégorie>-<numéro>`

---

## 2. Description générale

### 2.1 Perspective produit

uvforge est un outil de développeur (`dev tool`) destiné à être installé globalement via `uv tool install uvforge`. Il n'est jamais ajouté comme dépendance d'un projet cible.

```
┌──────────────────────────────────────────────┐
│  Développeur                                  │
│                                               │
│  $ uvforge init mylib                         │
│         │                                     │
│         ▼                                     │
│  ┌─────────────┐    génère    ┌────────────┐  │
│  │  uvforge    │ ──────────►  │  mylib/    │  │
│  │  (global)   │              │  Makefile  │  │
│  └─────────────┘              │  scripts/  │  │
│         │                     │  src/      │  │
│         │ appelle              │  tests/    │  │
│         ▼                     │  work/     │  │
│  ┌─────────────┐              └────────────┘  │
│  │  uv         │                              │
│  │  (global)   │                              │
│  └─────────────┘                              │
└──────────────────────────────────────────────┘
```

### 2.2 Fonctions principales

| ID | Fonction |
|---|---|
| F-01 | Initialiser un projet Python avec structure standard |
| F-02 | Générer les fichiers de configuration des outils qualité |
| F-03 | Installer les scripts de pipeline (`check.sh`, `publish.sh`, etc.) |
| F-04 | Générer un `Makefile` complet |
| F-05 | Configurer les dépendances dev via `uv` |
| F-06 | Auditer la conformité d'un projet existant |
| F-07 | Mettre à jour les scripts gérés vers la version courante |

### 2.3 Profil utilisateur

Développeur Python intermédiaire à expert, familier avec `uv`, les outils de qualité modernes (ruff, mypy) et les workflows basés sur `make`. Utilise macOS, Linux ou WSL.

### 2.4 Hypothèses et dépendances

- `uv` est installé et disponible dans le `PATH`
- `git` est installé (sauf si `--no-git` est spécifié)
- L'OS supporte les scripts shell Bash (`/bin/bash`)
- Python ≥ 3.12 est disponible dans l'environnement `uv`

---

## 3. Exigences fonctionnelles

### 3.1 `uvforge init`

#### REQ-INIT-01
uvforge SHALL accepter un argument optionnel `PROJECT_NAME`. Si absent, le nom est déduit du nom du répertoire courant.

#### REQ-INIT-02
uvforge SHALL créer les répertoires suivants dans le projet cible :
- `src/<package_name>/`
- `tests/`
- `scripts/`
- `work/`
- `doc/`

#### REQ-INIT-03
uvforge SHALL créer un fichier `work/.gitkeep` pour que le dossier `work/` soit tracké par git mais ignoré dans son contenu.

#### REQ-INIT-04
uvforge SHALL créer un `.gitignore` excluant au minimum : `work/*`, `!work/.gitkeep`, `__pycache__/`, `.mypy_cache/`, `dist/`, `*.egg-info/`, `.coverage`, `.env`.

#### REQ-INIT-05
uvforge SHALL générer un `pyproject.toml` contenant :
- Métadonnées projet (`name`, `version`, `description`, `requires-python`)
- Build system `hatchling`
- Groupe de dépendances `dev` avec : ruff, flake8, mypy, pytest, pytest-cov, bandit, pip-audit, twine
- Configuration de ruff (line-length=79, select="ALL", convention Google)
- Configuration de flake8 (max-complexity=10, max-line-length=79)
- Configuration mypy (strict=true)
- Configuration pytest (testpaths=["tests"], cov-fail-under=100)
- Configuration coverage (data_file dans `work/`)
- Configuration bandit (exclude_dirs=["tests","work"])
- Configuration des seuils de métriques (complexity=10, logical_lines=900)

#### REQ-INIT-06
uvforge SHALL générer un `Makefile` avec les cibles : `format`, `format-check`, `lint`, `flake8`, `docstrings`, `typecheck`, `metrics`, `security`, `test`, `check`, `ci`, `clean`, `clean-work`, `build`, `check-dist`, `publish-test`, `publish`.

#### REQ-INIT-07
uvforge SHALL copier les cinq scripts suivants dans `scripts/` :
`check.sh`, `check_docstrings.py`, `code_metrics.py`, `security_deps.sh`, `publish.sh`.

#### REQ-INIT-08
uvforge SHALL créer un `scripts/__init__.py` vide pour que mypy puisse analyser le répertoire.

#### REQ-INIT-09
uvforge SHALL créer `src/<package_name>/__init__.py` et `src/<package_name>/py.typed`.

#### REQ-INIT-10
uvforge SHALL créer `tests/__init__.py` et `tests/test_<package_name>.py` avec un test de smoke minimal.

#### REQ-INIT-11
uvforge SHALL créer un `README.md` minimal avec le nom du projet.

#### REQ-INIT-12
uvforge SHALL créer un `.python-version` contenant la version Python cible.

#### REQ-INIT-13
uvforge SHALL appeler `uv add --group dev` pour installer les dépendances dev.

#### REQ-INIT-14
uvforge SHALL appeler `uv sync` après avoir configuré les dépendances.

#### REQ-INIT-15
uvforge SHALL, sauf `--no-git`, initialiser un dépôt git et créer un commit initial.

#### REQ-INIT-16
uvforge SHALL refuser d'écraser un projet existant (présence de `pyproject.toml`) sans l'option `--force`.

#### REQ-INIT-17
uvforge SHALL afficher un résumé des actions effectuées et les prochaines étapes à l'issue de l'initialisation.

#### REQ-INIT-18
uvforge SHALL supporter l'option `--dry-run` qui affiche la liste des fichiers qui seraient créés sans effectuer aucune action.

#### REQ-INIT-19
Le nom du package Python SHALL être dérivé du `PROJECT_NAME` en remplaçant les `-` par `_` et en passant en minuscules.

### 3.2 `uvforge check`

#### REQ-CHECK-01
`uvforge check` SHALL vérifier la présence de chaque répertoire requis (`src/`, `tests/`, `scripts/`, `work/`, `doc/`).

#### REQ-CHECK-02
`uvforge check` SHALL vérifier la présence et l'exécutabilité de `scripts/check.sh`.

#### REQ-CHECK-03
`uvforge check` SHALL vérifier la présence de chaque script : `check_docstrings.py`, `code_metrics.py`, `security_deps.sh`, `publish.sh`.

#### REQ-CHECK-04
`uvforge check` SHALL vérifier que le `Makefile` contient les cibles obligatoires : `check`, `ci`, `test`, `lint`, `typecheck`, `build`, `publish`.

#### REQ-CHECK-05
`uvforge check` SHALL vérifier que `pyproject.toml` contient un groupe `dev` avec les outils requis.

#### REQ-CHECK-06
`uvforge check` SHALL vérifier la présence de `.python-version`.

#### REQ-CHECK-07
`uvforge check` SHALL vérifier que `work/.gitkeep` est présent.

#### REQ-CHECK-08
`uvforge check` SHALL afficher un rapport PASS/FAIL par item avec un code de sortie 0 (tout OK) ou 1 (au moins un FAIL).

#### REQ-CHECK-09
Avec l'option `--fix`, `uvforge check` SHALL recopier les scripts manquants depuis les templates embarqués.

### 3.3 `uvforge update`

#### REQ-UPDATE-01
`uvforge update` SHALL comparer chaque fichier géré (scripts, Makefile) avec la version embarquée dans uvforge.

#### REQ-UPDATE-02
Pour chaque fichier différent, `uvforge update` SHALL afficher un diff et proposer : remplacer / conserver / ignorer.

#### REQ-UPDATE-03
Avec l'option `--deps`, `uvforge update` SHALL mettre à jour les versions minimales des dépendances dev dans `pyproject.toml`.

---

## 4. Exigences non fonctionnelles

### 4.1 Performance

#### REQ-PERF-01
`uvforge init` SHALL se terminer en moins de 60 secondes sur une connexion internet standard (hors temps de téléchargement des dépendances pip par uv).

#### REQ-PERF-02
`uvforge check` SHALL se terminer en moins de 2 secondes.

### 4.2 Fiabilité

#### REQ-REL-01
En cas d'échec partiel de `uvforge init` (ex. uv non disponible), uvforge SHALL afficher un message d'erreur clair indiquant la cause et SHALL ne pas laisser de répertoire partiellement créé.

#### REQ-REL-02
`scripts/publish.sh` SHALL garantir la suppression de `work/dist/` en toutes circonstances (trap EXIT).

### 4.3 Utilisabilité

#### REQ-USE-01
Toute sortie terminal SHALL utiliser des couleurs pour distinguer succès (vert), avertissement (jaune) et erreur (rouge).

#### REQ-USE-02
`uvforge --help` et `uvforge <command> --help` SHALL afficher une aide claire avec la liste des options.

#### REQ-USE-03
uvforge SHALL fournir une autocomplétion shell (bash, zsh, fish) via `uvforge --install-completion`.

### 4.4 Maintenabilité

#### REQ-MAIN-01
Le code de uvforge SHALL respecter les mêmes standards qualité que ceux qu'il impose aux projets cibles (ruff, mypy strict, couverture 100%).

#### REQ-MAIN-02
Chaque module Python de uvforge SHALL avoir une couverture de tests ≥ 100%.

### 4.5 Portabilité

#### REQ-PORT-01
uvforge SHALL fonctionner sur macOS (≥ 13), Linux (Ubuntu ≥ 22.04), et Windows via WSL2.

#### REQ-PORT-02
Les scripts shell générés SHALL utiliser `#!/usr/bin/env bash` et fonctionner avec Bash ≥ 4.

---

## 5. Contraintes système

### 5.1 Environnement d'exécution

| Composant | Version minimale |
|---|---|
| Python | 3.12 |
| uv | 0.5 |
| git | 2.30 |
| Bash | 4.0 |

### 5.2 Installation

uvforge SHALL s'installer via `uv tool install uvforge` sans nécessiter de droits administrateurs.

### 5.3 Absence de dépendances runtime dans les projets cibles

uvforge NE SHALL PAS apparaître dans `dependencies` (ni dans `dev`) d'un projet qu'il a initialisé.

---

## 6. Exigences sur les scripts embarqués

### 6.1 `scripts/check.sh`

#### REQ-SCR-01
`check.sh` SHALL exécuter les 9 vérifications dans l'ordre suivant :
format → lint (ruff) → flake8 → docstrings → typecheck → metrics → security (bandit) → security-deps (pip-audit) → test (pytest+coverage).

#### REQ-SCR-02
`check.sh` SHALL supporter le mode `--ci` dans lequel le format est vérifié sans modification du code.

#### REQ-SCR-03
`check.sh` SHALL écrire les logs de chaque vérification dans des fichiers séparés dans `work/`.

#### REQ-SCR-04
`check.sh` SHALL afficher un résumé coloré PASS/FAIL par vérification.

#### REQ-SCR-05
`check.sh` SHALL, en cas d'échec, afficher le détail des logs des vérifications échouées.

#### REQ-SCR-06
`check.sh` SHALL retourner un code de sortie égal au nombre de vérifications échouées.

### 6.2 `scripts/check_docstrings.py`

#### REQ-SCR-10
`check_docstrings.py` SHALL analyser `src/`, `tests/` et `scripts/` via l'AST Python.

#### REQ-SCR-11
`check_docstrings.py` SHALL signaler comme violation toute fonction privée (`_xxx`) sans docstring.

#### REQ-SCR-12
`check_docstrings.py` SHALL signaler comme violation toute fonction de test (`test_xxx`) dont le docstring ne contient pas `"Requirement:"`.

#### REQ-SCR-13
`check_docstrings.py` SHALL afficher les violations au format `path:line: name: message`.

### 6.3 `scripts/code_metrics.py`

#### REQ-SCR-20
`code_metrics.py` SHALL calculer la complexité cyclomatique de chaque fonction/méthode.

#### REQ-SCR-21
`code_metrics.py` SHALL calculer le nombre de lignes logiques par module.

#### REQ-SCR-22
`code_metrics.py` SHALL lire les seuils depuis `pyproject.toml` (`[tool.metrics]`).

#### REQ-SCR-23
`code_metrics.py` SHALL retourner code 1 si un seuil est dépassé.

### 6.4 `scripts/security_deps.sh`

#### REQ-SCR-30
`security_deps.sh` SHALL exporter les dépendances runtime dans `work/requirements.txt`.

#### REQ-SCR-31
`security_deps.sh` SHALL passer sans erreur si le projet n'a aucune dépendance runtime.

#### REQ-SCR-32
`security_deps.sh` SHALL exécuter `pip-audit --strict` sur les dépendances exportées.

### 6.5 `scripts/publish.sh`

#### REQ-SCR-40
`publish.sh` SHALL accepter un paramètre `ACTION` parmi : `build`, `check-dist`, `publish-test`, `publish`.

#### REQ-SCR-41
`publish.sh` SHALL construire le package dans `work/dist/` via `uv build`.

#### REQ-SCR-42
`publish.sh` SHALL valider le package avec `twine check` avant toute publication.

#### REQ-SCR-43
`publish.sh` SHALL supprimer `work/dist/` à la fin de l'exécution (succès ou échec) via `trap`.

#### REQ-SCR-44
`publish.sh` SHALL publier sur TestPyPI avec l'action `publish-test` et sur PyPI avec `publish`.

---

## 7. Exigences de test

### 7.1 Tests unitaires des modules uvforge

#### REQ-TEST-01
Chaque module Python de uvforge (`scaffold.py`, `renderer.py`, `uv_runner.py`, `init.py`, `check.py`, `update.py`) SHALL avoir des tests unitaires couvrant 100% des branches.

#### REQ-TEST-02
Les tests SHALL utiliser `tmp_path` (pytest) pour isoler les opérations sur le système de fichiers.

#### REQ-TEST-03
Les appels à `uv` (subprocess) SHALL être mockés dans les tests unitaires.

### 7.2 Tests des scripts embarqués

#### REQ-TEST-10
`check_docstrings.py` SHALL être testé avec des cas de fixtures Python synthétiques (fonctions avec/sans docstring, tests avec/sans "Requirement:").

#### REQ-TEST-11
`code_metrics.py` SHALL être testé avec des fixtures de code Python dont la complexité et les lignes logiques sont connues.

#### REQ-TEST-12
`publish.sh` SHALL être testé via un projet minimal dans `tmp_path` vérifiant :
- La création de `work/dist/` avec les artefacts
- La suppression de `work/dist/` après exécution
- Le comportement avec `ACTION=build` (pas d'upload)

#### REQ-TEST-13
`security_deps.sh` SHALL être testé avec un projet sans dépendances runtime (exit 0 attendu).

### 7.3 Tests d'intégration

#### REQ-TEST-20
Un test d'intégration SHALL exécuter `uvforge init` dans un `tmp_path`, puis vérifier que `make check` retourne 0.

#### REQ-TEST-21
Un test d'intégration SHALL vérifier que `uvforge check` retourne 0 sur un projet fraîchement initialisé.

### 7.4 Couverture

#### REQ-TEST-30
La couverture globale de uvforge SHALL être ≥ 100% (branches incluses).

---

## 8. Glossaire

| Terme | Définition |
|---|---|
| **dev tool** | Outil installé globalement pour le développeur, non présent dans les dépendances des projets |
| **scaffold** | Création de la structure de répertoires et fichiers d'un projet |
| **pipeline qualité** | Séquence de vérifications automatiques (format, lint, type, test, sécurité) |
| **work/** | Répertoire de sorties temporaires (logs, coverage, dist) ignoré par `.gitignore` |
| **template** | Fichier avec variables Jinja2 embarqué dans uvforge et rendu lors de l'init |
| **uv** | Gestionnaire de packages et d'environnements Python développé par Astral |
| **hatchling** | Backend de build Python moderne, utilisé par défaut avec uv |
