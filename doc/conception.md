# yggtools — Document de Conception

**Version :** 0.1.0  
**Date :** 2026-06-12  
**Auteur :** Antoine Barré

---

## 1. Vision et objectif

`yggtools` est un outil de développement (dev tool) qui vient **surcharger `uv`** pour fournir une couche d'organisation, de scripts de qualité et de pipeline CI reproductible. Il ne s'installe pas comme dépendance d'un projet cible : il s'utilise globalement (ou dans l'environnement dev) pour **initialiser** et **maintenir** la structure d'un package Python selon un standard opinionné.

L'inspiration directe est [mkforge](https://github.com/antoinebarre/mkforge) : même philosophie de pipeline `make`, même ensemble d'outils (ruff, flake8, mypy, bandit, pytest, pip-audit), même structure de répertoires `src/`.

### Ce que yggtools fait

- Initialise un package Python avec la structure standard (`src/`, `tests/`, `scripts/`, `work/`, `doc/`)
- Génère les fichiers de configuration des outils (`pyproject.toml`, `.python-version`, `.gitignore`)
- Installe les scripts de qualité (`scripts/check.sh`, `scripts/check_docstrings.py`, `scripts/code_metrics.py`, `scripts/security_deps.sh`)
- Génère un `Makefile` avec toutes les cibles du pipeline
- Configure `uv` (dépendances dev, groupes)
- S'assure que le projet peut passer un `make check` dès la création

### Ce que yggtools ne fait pas

- Ne s'ajoute pas au `dependencies` du projet cible
- Ne modifie pas `uv` lui-même

---

## 2. Interface principale

### Commande racine

```
yggtools <command> [options]
```

### Commandes

| Commande | Description |
|---|---|
| `yggtools init` | Initialise un nouveau package dans le répertoire courant (ou `<name>`) |
| `yggtools check` | Vérifie que la structure du projet est conforme (audit) |
| `yggtools update` | Met à jour les scripts et Makefile depuis les templates intégrés |

### `yggtools init` — interface détaillée

```
yggtools init [PROJECT_NAME] [OPTIONS]

Arguments:
  PROJECT_NAME    Nom du package (optionnel, défaut = nom du dossier courant)

Options:
  --python TEXT   Version Python cible (défaut = version active via uv)
  --no-git        Ne pas initialiser un dépôt git
  --force         Écrase les fichiers existants sans confirmation
  --dry-run       Affiche ce qui serait créé sans rien écrire
```

**Exemple :**
```bash
mkdir mylib && cd mylib
yggtools init
# ou directement :
yggtools init mylib
```

### `yggtools check` — interface détaillée

```
yggtools check [OPTIONS]

Options:
  --fix     Tente de corriger les écarts détectés (recopy des scripts manquants)
```

Vérifie la présence et la conformité de :
- Structure des répertoires
- `Makefile` (présence des cibles obligatoires)
- Scripts dans `scripts/`
- Groupes de dépendances dev dans `pyproject.toml`

### `yggtools update`

Met à jour les fichiers gérés par yggtools (scripts, Makefile) avec la dernière version embarquée dans le package. Protège les fichiers modifiés par l'utilisateur avec un diff interactif.

---

## 3. Structure générée dans le projet cible

Après `yggtools init mylib`, le répertoire résultant est :

```
mylib/
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock                  (généré par uv après sync)
├── README.md
├── Makefile
├── doc/
│   └── .gitkeep
├── work/
│   ├── .gitkeep             (préserve le dossier dans git)
│   └── dist/                (artefacts de build, créé à la demande)
├── scripts/
│   ├── __init__.py
│   ├── check.sh             (pipeline qualité complet)
│   ├── check_docstrings.py  (validation des docstrings)
│   ├── code_metrics.py      (métriques de complexité)
│   ├── security_deps.sh     (audit sécurité dépendances)
│   └── publish.sh           (build, validation et publication PyPI)
├── src/
│   └── mylib/
│       ├── __init__.py
│       └── py.typed
└── tests/
    ├── __init__.py
    └── test_mylib.py        (test de smoke vide)
```

---

## 4. Pipeline qualité — Makefile

Le `Makefile` généré reproduit fidèlement le pipeline de mkforge.

### Cibles

| Cible | Commande | Description |
|---|---|---|
| `format` | `uv run ruff format $(PYTHON_FILES)` | Formate le code |
| `format-check` | `uv run ruff format --check $(PYTHON_FILES)` | Vérifie le format (sans modifier) |
| `lint` | `uv run ruff check $(PYTHON_FILES)` | Lint ruff |
| `flake8` | `uv run flake8 $(PYTHON_FILES)` | Lint flake8 (complexité cyclomatique) |
| `docstrings` | `uv run python scripts/check_docstrings.py` | Validation des docstrings |
| `typecheck` | `uv run mypy src tests scripts` | Typage statique strict |
| `metrics` | `uv run python scripts/code_metrics.py` | Métriques de code |
| `security` | `uv run bandit ...` + `scripts/security_deps.sh` | Sécurité (bandit + pip-audit) |
| `test` | `uv run pytest` | Tests unitaires + couverture 100% |
| `check` | `bash scripts/check.sh` | Pipeline complet (local, formate) |
| `ci` | `bash scripts/check.sh --ci` | Pipeline complet (CI, pas de format) |
| `clean` | Supprime `work/*` sauf `.gitkeep` | Nettoyage |
| `build` | `bash scripts/publish.sh build` | Build wheel/sdist dans `work/dist/` |
| `check-dist` | `bash scripts/publish.sh check-dist` | Validation du package |
| `publish-test` | `bash scripts/publish.sh publish-test` | Publication sur TestPyPI |
| `publish` | `bash scripts/publish.sh publish` | Publication sur PyPI |

### Variable `PYTHON_FILES`

```makefile
PYTHON_FILES = src tests scripts
```

### Dépendance implicite

Toutes les cibles de qualité dépendent de `clean` pour repartir d'un état propre dans `work/`.

---

## 5. Configuration `pyproject.toml` générée

```toml
[project]
name = "{{ project_name }}"
version = "0.1.0"
description = ""
readme = "README.md"
requires-python = ">={{ python_version }}"
license = { text = "MIT" }
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{{ project_name }}"]

[dependency-groups]
dev = [
  "ruff>=0.9",
  "flake8>=7",
  "mypy>=1.14",
  "pytest>=8",
  "pytest-cov>=6",
  "bandit>=1.8",
  "pip-audit>=2.8",
  "twine>=6",
]

# --- ruff ---
[tool.ruff]
line-length = 79

[tool.ruff.lint]
select = ["ALL"]
ignore = ["TC001", "TC002", "TC003", "TC004"]

[tool.ruff.lint.pydocstyle]
convention = "google"

# --- flake8 ---
[tool.flake8]
max-complexity = 10
max-line-length = 79

# --- mypy ---
[tool.mypy]
strict = true

# --- pytest ---
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=100"

[tool.coverage.run]
data_file = "work/.coverage"

[tool.coverage.report]
show_missing = true

# --- bandit ---
[tool.bandit]
exclude_dirs = ["tests", "work"]
```

---

## 6. Scripts embarqués

Les scripts sont des **ressources statiques** incluses dans le package yggtools (via `importlib.resources`) et copiées lors du `init`.

### `scripts/check.sh`

Orchestre tous les checks en séquence avec :
- Sortie colorée (PASS / FAIL)
- Mode `--ci` (pas de reformatage)
- Rapport des détails en cas d'échec
- Sortie avec code 0 (tout OK) ou 1 (au moins un échec)

**Ordre des checks :**
1. `format` (ou `format-check` en mode CI)
2. `lint` (ruff)
3. `flake8`
4. `docstrings`
5. `typecheck` (mypy)
6. `metrics`
7. `security` (bandit)
8. `security-deps` (pip-audit)
9. `test` (pytest + couverture)

### `scripts/check_docstrings.py`

Parcourt l'AST Python de `src/`, `tests/`, `scripts/` et vérifie :
- Les fonctions privées (`_xxx`) ont un docstring Google-style
- Les fonctions de test (`test_xxx`) contiennent `"Requirement:"` dans leur docstring

### `scripts/code_metrics.py`

Calcule et affiche la complexité cyclomatique et le nombre de lignes logiques par module. Échoue si les seuils définis dans `pyproject.toml` sont dépassés.

### `scripts/security_deps.sh`

Lance `uv run pip-audit` et vérifie l'absence de CVE dans les dépendances.

Séquence :
1. `uv export --no-dev --no-hashes --format requirements-txt` → `work/requirements.txt`
2. Si aucune dépendance runtime : exit 0 avec message
3. `uv run pip-audit --strict --requirement work/requirements.txt`

### `scripts/publish.sh`

Automatise le cycle build → validation → publication avec nettoyage garanti.

Paramètre `ACTION` : `build` | `check-dist` | `publish-test` | `publish`

Séquence :
1. `trap cleanup EXIT` pour nettoyage de `work/dist/` en toutes circonstances
2. `mkdir -p work/dist`
3. `uv build --out-dir work/dist`
4. `uv run twine check work/dist/*`
5. Selon `ACTION` :
   - `build` / `check-dist` : s'arrête ici
   - `publish-test` : `uv run twine upload --repository testpypi work/dist/*`
   - `publish` : `uv run twine upload work/dist/*`

---

## 7. Architecture interne de yggtools

```
yggtools/
├── src/
│   └── yggtools/
│       ├── __init__.py
│       ├── cli.py           # Point d'entrée Click/Typer
│       ├── init.py          # Logique métier de yggtools init
│       ├── check.py         # Logique métier de yggtools check
│       ├── update.py        # Logique métier de yggtools update
│       ├── renderer.py      # Rendu des templates (Jinja2 ou string.Template)
│       ├── scaffold.py      # Création des répertoires et fichiers
│       ├── uv_runner.py     # Appels subprocess à uv
│       └── templates/       # Ressources statiques (scripts, Makefile, configs)
│           ├── scripts/
│           │   ├── check.sh
│           │   ├── check_docstrings.py
│           │   ├── code_metrics.py
│           │   ├── security_deps.sh
│           │   └── publish.sh
│           ├── Makefile.tmpl
│           ├── pyproject.toml.tmpl
│           ├── gitignore.tmpl
│           └── README.md.tmpl
├── tests/
├── scripts/
├── Makefile
└── pyproject.toml
```

### Dépendances de yggtools lui-même

| Package | Rôle |
|---|---|
| `typer` | CLI avec autocomplétion et aide générée |
| `rich` | Sortie terminal colorée |
| `jinja2` | Rendu des templates |

Uvforge ne dépend pas des outils qu'il installe (ruff, mypy, etc.) — ceux-ci sont injectés dans le projet cible via `uv add --group dev`.

---

## 8. Logique métier — `yggtools init`

### Algorithme

```
1. Résoudre le nom du projet (argument CLI ou nom du dossier courant)
2. Vérifier que le dossier cible est vide ou utiliser --force
3. Vérifier que uv est disponible dans le PATH
4. Créer l'arborescence des répertoires (scaffold)
5. Rendre et écrire les fichiers de configuration depuis les templates
6. Copier les scripts depuis yggtools/templates/scripts/
7. Appeler `uv init --lib --name <project_name>` si pas déjà initialisé,
   ou adapter pyproject.toml si uv init déjà fait
8. Appeler `uv add --group dev ruff flake8 mypy pytest pytest-cov bandit pip-audit twine`
9. Appeler `uv sync`
10. Si --no-git absent : appeler `git init && git add . && git commit -m "chore: yggtools init"`
11. Afficher le résumé avec les prochaines étapes
```

### Règles de résolution du nom

- Le nom du package Python = `project_name` avec les `-` remplacés par `_`
- Le nom du répertoire créé = `project_name` tel que fourni

### Détection de conflit

Si le répertoire cible contient déjà un `pyproject.toml`, yggtools demande confirmation avant de continuer (sauf `--force`).

---

## 9. Logique métier — `yggtools check`

Parcourt le projet courant et vérifie :

| Élément | Vérification |
|---|---|
| `src/<name>/` | Répertoire existe |
| `tests/` | Répertoire existe |
| `scripts/check.sh` | Fichier existe et est exécutable |
| `scripts/check_docstrings.py` | Fichier existe |
| `scripts/code_metrics.py` | Fichier existe |
| `Makefile` | Contient les cibles `check`, `ci`, `test`, `lint`, `typecheck` |
| `pyproject.toml` | Groupe `dev` présent avec les outils requis |
| `.python-version` | Fichier présent |

Retourne un rapport coloré avec PASS/FAIL par item.

---

## 10. Logique métier — `yggtools update`

1. Pour chaque fichier géré (scripts, Makefile) :
   - Compare le contenu actuel avec la version embarquée dans yggtools
   - Si différent : affiche un diff et propose de remplacer / conserver / ignorer
2. Met à jour les versions des dépendances dev dans `pyproject.toml` (optionnel, `--deps`)

---

## 11. Étapes de développement

### Phase 1 — Fondations (MVP)

- [ ] Structure du package yggtools avec `src/` layout
- [ ] CLI `typer` avec commande `init`
- [ ] `scaffold.py` : création des répertoires (y compris `work/` avec `.gitkeep`)
- [ ] `renderer.py` : rendu des templates Jinja2
- [ ] Templates : `pyproject.toml.tmpl`, `Makefile.tmpl`, `.gitignore.tmpl`, `README.md.tmpl`
- [ ] Scripts copiés : `check.sh`, `check_docstrings.py`, `code_metrics.py`, `security_deps.sh`, `publish.sh`
- [ ] `uv_runner.py` : appels `uv add`, `uv sync`
- [ ] Tests unitaires de chaque module yggtools
- [ ] Tests des scripts embarqués (docstrings, metrics, publish) via subprocess dans tmpdir

### Phase 2 — Robustesse

- [ ] Commande `yggtools check`
- [ ] Gestion `--force`, `--dry-run`, `--no-git`
- [ ] Détection de conflit et confirmation interactive
- [ ] Messages d'erreur `rich` bien formatés
- [ ] Tests d'intégration bout-en-bout (créer un projet dans tmpdir, vérifier `make check` passe)

### Phase 3 — Maintenance

- [ ] Commande `yggtools update`
- [ ] Autocomplétion shell (typer natif)
- [ ] Publication sur PyPI pour installation globale via `uv tool install yggtools`

---

## 12. Installation et usage global

yggtools est conçu pour s'installer globalement via :

```bash
uv tool install yggtools
```

Cela le rend disponible comme commande système sans polluer aucun projet. L'utilisateur n'a jamais besoin d'ajouter `yggtools` aux dépendances de ses projets.

---

## 13. Décisions techniques

| Décision | Choix | Justification |
|---|---|---|
| CLI framework | `typer` | Typage natif, autocomplétion, aide auto-générée |
| Rendu templates | `jinja2` | Standard, puissant, connu |
| Sortie terminal | `rich` | Cohérent avec l'écosystème uv/ruff |
| Appels uv | `subprocess` | uv est un binaire externe, pas de SDK Python |
| Scripts embarqués | `importlib.resources` | Standard Python 3.9+, compatible avec les wheels |
| Layout | `src/` | Best practice moderne, cohérent avec mkforge |
| Build backend | `hatchling` | Natif uv, pas de setuptools |
