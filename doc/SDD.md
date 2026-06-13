# SDD — Software Design Document

**Projet :** uvforge  
**Version :** 1.0  
**Date :** 2026-06-12  
**Auteur :** Antoine Barré  
**Statut :** Draft

---

## Table des matières

1. [Contexte et objectifs de conception](#1-contexte-et-objectifs-de-conception)
2. [Architecture générale](#2-architecture-générale)
3. [Modules Python](#3-modules-python)
4. [Templates et ressources embarquées](#4-templates-et-ressources-embarquées)
5. [Scripts embarqués — conception détaillée](#5-scripts-embarqués--conception-détaillée)
6. [Interface CLI](#6-interface-cli)
7. [Flux d'exécution](#7-flux-dexécution)
8. [Gestion des erreurs](#8-gestion-des-erreurs)
9. [Stratégie de test](#9-stratégie-de-test)
10. [Décisions de conception](#10-décisions-de-conception)

---

## 1. Contexte et objectifs de conception

### 1.1 Objectifs

- **Minimalisme** : uvforge doit dépendre du minimum de packages externes.
- **Reproductibilité** : deux `uvforge init` avec les mêmes paramètres produisent des projets identiques.
- **Testabilité** : chaque module est indépendant et testable sans effets de bord.
- **Extensibilité** : ajouter un nouveau script ou template ne nécessite pas de modifier la logique métier.

### 1.2 Contraintes de conception

- Les scripts embarqués sont des fichiers statiques, pas du code généré dynamiquement.
- Les appels à `uv` et `git` se font via `subprocess` — aucun binding Python n'est disponible.
- uvforge ne modifie jamais `uv` ni ses fichiers de configuration.

---

## 2. Architecture générale

### 2.1 Vue d'ensemble des couches

```
┌─────────────────────────────────────────────────────┐
│  COUCHE CLI  (cli.py — Typer)                        │
│  Parsing des arguments, validation de surface,       │
│  orchestration des commandes                         │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┼─────────────────┐
         ▼             ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  init.py     │ │  check.py    │ │  update.py   │
│  (logique    │ │  (logique    │ │  (logique    │
│   init)      │ │   check)     │ │   update)    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ scaffold.py  │ │ renderer.py  │ │ uv_runner.py │
│ (filesystem) │ │ (templates)  │ │ (subprocess) │
└──────────────┘ └──────────────┘ └──────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │  templates/      │
              │  (ressources     │
              │   statiques)     │
              └──────────────────┘
```

### 2.2 Structure du package uvforge

```
src/uvforge/
├── __init__.py          # version, __all__
├── cli.py               # point d'entrée Typer
├── init.py              # orchestration de uvforge init
├── check.py             # orchestration de uvforge check
├── update.py            # orchestration de uvforge update
├── scaffold.py          # opérations filesystem
├── renderer.py          # rendu des templates Jinja2
├── uv_runner.py         # wrapper subprocess uv/git
├── models.py            # dataclasses partagées
└── templates/           # ressources statiques (MANIFEST)
    ├── scripts/
    │   ├── check.sh
    │   ├── check_docstrings.py
    │   ├── code_metrics.py
    │   ├── security_deps.sh
    │   └── publish.sh
    ├── Makefile.tmpl
    ├── pyproject.toml.tmpl
    ├── gitignore.tmpl
    └── README.md.tmpl
```

---

## 3. Modules Python

### 3.1 `models.py`

Contient les types de données partagés entre les modules.

```python
@dataclass
class ProjectContext:
    """Contexte complet d'un projet uvforge."""
    project_name: str        # "my-lib"
    package_name: str        # "my_lib"
    python_version: str      # "3.12"
    project_dir: Path        # chemin absolu du projet cible
    dry_run: bool = False
    force: bool = False
    no_git: bool = False

@dataclass
class CheckResult:
    """Résultat d'une vérification uvforge check."""
    label: str
    passed: bool
    detail: str = ""

@dataclass
class ScriptFile:
    """Métadonnées d'un script embarqué."""
    name: str          # "check.sh"
    executable: bool   # True pour les .sh
```

### 3.2 `scaffold.py`

Responsable uniquement des opérations sur le système de fichiers. N'interprète pas les templates.

**Interface publique :**

```python
def create_directories(ctx: ProjectContext) -> list[Path]:
    """Crée l'arborescence de répertoires. Retourne les chemins créés."""

def write_file(path: Path, content: str, *, executable: bool = False) -> None:
    """Écrit un fichier. Crée les parents si nécessaire."""

def copy_script(source: Path, dest: Path) -> None:
    """Copie un script et applique chmod +x."""

def ensure_gitkeep(directory: Path) -> None:
    """Crée directory/.gitkeep si le fichier n'existe pas."""
```

**Répertoires créés :**

| Chemin | Fichiers créés automatiquement |
|---|---|
| `src/<package_name>/` | `__init__.py`, `py.typed` |
| `tests/` | `__init__.py`, `test_<package_name>.py` |
| `scripts/` | `__init__.py` |
| `work/` | `.gitkeep` |
| `doc/` | `.gitkeep` |

**Mode dry-run :** Si `ctx.dry_run is True`, toutes les fonctions logguent l'action sans l'exécuter.

### 3.3 `renderer.py`

Charge et rend les templates Jinja2 embarqués via `importlib.resources`.

**Interface publique :**

```python
def render_template(template_name: str, ctx: ProjectContext) -> str:
    """Charge et rend un template depuis uvforge/templates/."""

def list_templates() -> list[str]:
    """Retourne les noms de templates disponibles."""
```

**Variables Jinja2 disponibles dans les templates :**

| Variable | Valeur |
|---|---|
| `{{ project_name }}` | Nom du projet (`my-lib`) |
| `{{ package_name }}` | Nom du package Python (`my_lib`) |
| `{{ python_version }}` | Version Python (`3.12`) |
| `{{ uvforge_version }}` | Version de uvforge ayant généré le projet |

**Chargement des ressources :**

```python
from importlib.resources import files

def _load_template(name: str) -> str:
    return files("uvforge.templates").joinpath(name).read_text(encoding="utf-8")
```

### 3.4 `uv_runner.py`

Encapsule tous les appels externes (`uv`, `git`). Facilite le mock dans les tests.

**Interface publique :**

```python
def check_uv_available() -> None:
    """Lève UvNotFoundError si uv n'est pas dans le PATH."""

def uv_add_dev_deps(project_dir: Path, deps: list[str]) -> None:
    """Appelle uv add --group dev <deps>."""

def uv_sync(project_dir: Path) -> None:
    """Appelle uv sync."""

def git_init(project_dir: Path) -> None:
    """Appelle git init."""

def git_add_all(project_dir: Path) -> None:
    """Appelle git add -A."""

def git_commit(project_dir: Path, message: str) -> None:
    """Appelle git commit -m <message>."""

def run_command(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Exécute une commande et retourne le résultat. Lève CommandError en cas d'échec."""
```

**DEV_DEPS — liste fixe des dépendances dev :**

```python
DEV_DEPS: list[str] = [
    "ruff>=0.9",
    "flake8>=7",
    "mypy>=1.14",
    "pytest>=8",
    "pytest-cov>=6",
    "bandit>=1.8",
    "pip-audit>=2.8",
    "twine>=6",
]
```

### 3.5 `init.py`

Orchestre le workflow complet de `uvforge init`. Appelle scaffold, renderer et uv_runner dans l'ordre.

**Interface publique :**

```python
def run_init(ctx: ProjectContext) -> None:
    """Exécute l'initialisation complète. Lève InitError en cas d'échec."""
```

**Algorithme détaillé :**

```
_validate_preconditions(ctx)
  ├── check_uv_available()
  ├── si ctx.project_dir existe et contient pyproject.toml et pas ctx.force → raise ConflictError
  └── si ctx.dry_run → afficher plan et retourner

create_directories(ctx)
  └── [src/<pkg>/, tests/, scripts/, work/, doc/]

_write_config_files(ctx)
  ├── render_template("pyproject.toml.tmpl", ctx) → write "pyproject.toml"
  ├── render_template("Makefile.tmpl", ctx)       → write "Makefile"
  ├── render_template("gitignore.tmpl", ctx)      → write ".gitignore"
  ├── render_template("README.md.tmpl", ctx)      → write "README.md"
  └── write ".python-version" ← ctx.python_version

_copy_scripts(ctx)
  └── pour chaque script dans templates/scripts/ → copy_script(src, dst)

_install_dev_deps(ctx)
  ├── uv_add_dev_deps(ctx.project_dir, DEV_DEPS)
  └── uv_sync(ctx.project_dir)

_init_git(ctx)            [si pas ctx.no_git]
  ├── git_init(ctx.project_dir)
  ├── git_add_all(ctx.project_dir)
  └── git_commit(ctx.project_dir, "chore: uvforge init")

_print_summary(ctx)
```

### 3.6 `check.py`

Inspecte un projet existant et produit une liste de `CheckResult`.

**Interface publique :**

```python
def run_check(project_dir: Path, fix: bool = False) -> list[CheckResult]:
    """Audite le projet et retourne les résultats. Applique fix si demandé."""
```

**Vérifications effectuées :**

```python
CHECKS: list[Callable[[Path], CheckResult]] = [
    _check_src_dir,
    _check_tests_dir,
    _check_scripts_dir,
    _check_work_gitkeep,
    _check_script_check_sh,
    _check_script_check_docstrings,
    _check_script_code_metrics,
    _check_script_security_deps,
    _check_script_publish,
    _check_makefile_targets,
    _check_pyproject_dev_group,
    _check_python_version_file,
]
```

### 3.7 `update.py`

Compare les fichiers gérés et propose des mises à jour.

**Interface publique :**

```python
def run_update(project_dir: Path, update_deps: bool = False) -> None:
    """Compare et met à jour les fichiers gérés interactivement."""
```

**Fichiers gérés :**

```python
MANAGED_FILES: list[str] = [
    "Makefile",
    "scripts/check.sh",
    "scripts/check_docstrings.py",
    "scripts/code_metrics.py",
    "scripts/security_deps.sh",
    "scripts/publish.sh",
]
```

---

## 4. Templates et ressources embarquées

### 4.1 Déclaration dans `pyproject.toml`

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/uvforge"]

[tool.hatch.build.targets.wheel.force-include]
"src/uvforge/templates" = "uvforge/templates"
```

Les scripts dans `templates/scripts/` sont des fichiers **statiques** (non-templates Jinja2) — ils sont copiés tels quels.

Les fichiers `.tmpl` sont des templates Jinja2.

### 4.2 Accès depuis le code

```python
from importlib.resources import files, as_file

# Lecture d'un template
content = files("uvforge.templates").joinpath("Makefile.tmpl").read_text()

# Copie d'un script
with as_file(files("uvforge.templates.scripts").joinpath("check.sh")) as src:
    shutil.copy2(src, dest)
    dest.chmod(dest.stat().st_mode | 0o111)
```

### 4.3 Template `Makefile.tmpl`

Variables utilisées : `{{ package_name }}`

Cibles définies et leurs dépendances :

```
.PHONY: format format-check lint flake8 docstrings typecheck metrics security test check ci clean clean-work build check-dist publish-test publish

PYTHON_FILES := src tests scripts

clean-work:
    find work -not -name '.gitkeep' -not -name 'work' -delete

clean: clean-work

format: clean-work
    uv run ruff format $(PYTHON_FILES)

format-check: clean-work
    uv run ruff format --check $(PYTHON_FILES)

lint: clean-work
    uv run ruff check $(PYTHON_FILES)

flake8: clean-work
    uv run flake8 $(PYTHON_FILES)

docstrings: clean-work
    uv run python scripts/check_docstrings.py

typecheck: clean-work
    uv run mypy src tests scripts

metrics: clean-work
    uv run python scripts/code_metrics.py

security: clean-work
    uv run bandit -r src -x tests,work
    bash scripts/security_deps.sh

test: clean-work
    uv run pytest

check: clean-work
    bash scripts/check.sh

ci: clean-work
    bash scripts/check.sh --ci

build: clean-work
    bash scripts/publish.sh build

check-dist: clean-work
    bash scripts/publish.sh check-dist

publish-test: clean-work
    bash scripts/publish.sh publish-test

publish: clean-work
    bash scripts/publish.sh publish
```

### 4.4 Template `pyproject.toml.tmpl`

Voir section 5 du document de conception. Variables : `{{ project_name }}`, `{{ package_name }}`, `{{ python_version }}`.

---

## 5. Scripts embarqués — conception détaillée

### 5.1 `check.sh` — structure interne

```bash
#!/usr/bin/env bash
set -euo pipefail

# Couleurs
GREEN='\033[0;32m'; RED='\033[0;31m'; RESET='\033[0m'
SEP="─────────────────────────────────────────"

# Mode CI ou local
MODE="${1:-local}"

# Nettoyage des logs précédents
find work -name "*.log" -delete 2>/dev/null || true

PASS=0; FAIL=0

run() {
    local label="$1"; shift
    local log="work/${label// /_}.log"
    if "$@" > "$log" 2>&1; then
        echo -e "${GREEN}✓ PASS${RESET} — $label"
        PASS=$((PASS+1))
    else
        echo -e "${RED}✗ FAIL${RESET} — $label"
        FAIL=$((FAIL+1))
    fi
}

# Checks
if [ "$MODE" = "--ci" ]; then
    run "format"      uv run ruff format --check src tests scripts
else
    run "format"      uv run ruff format src tests scripts
fi
run "lint"            uv run ruff check src tests scripts
run "flake8"          uv run flake8 src tests scripts
run "docstrings"      uv run python scripts/check_docstrings.py
run "typecheck"       uv run mypy src tests scripts
run "metrics"         uv run python scripts/code_metrics.py
run "security"        uv run bandit -r src -x tests,work
run "security-deps"   bash scripts/security_deps.sh
run "test"            uv run pytest

# Rapport final
echo "$SEP"
echo "Résultat : $PASS PASS — $FAIL FAIL"

if [ "$FAIL" -gt 0 ]; then
    echo -e "\n${RED}Détails des échecs :${RESET}"
    for log in work/*.log; do
        if grep -q "FAIL" "$log" 2>/dev/null; then
            echo -e "\n─── $(basename "$log") ───"
            cat "$log"
        fi
    done
fi

exit "$FAIL"
```

### 5.2 `check_docstrings.py` — structure interne

```
main()
 ├── scan_directories(SOURCE_ROOTS=["src","tests","scripts"])
 │    └── pour chaque .py → parse_file(path)
 │         └── ast.walk(tree)
 │              ├── FunctionDef / AsyncFunctionDef
 │              │    ├── si name starts with "_" → check_has_docstring()
 │              │    └── si name starts with "test_" → check_requirement_in_docstring()
 │              └── CollectIssues → list[DocstringIssue]
 └── si issues → print "path:line: name: message", exit(1)
     sinon → print "OK", exit(0)
```

**Dataclasse :**
```python
@dataclass
class DocstringIssue:
    path: Path
    line: int
    name: str
    message: str
```

### 5.3 `code_metrics.py` — structure interne

```
main()
 ├── load_config("pyproject.toml") → MetricsConfig
 │    └── [tool.metrics] max_complexity, max_logical_lines
 ├── pour chaque .py dans src/ tests/ scripts/
 │    └── _file_metric(path) → FileMetric
 │         ├── _logical_line_count(tree)
 │         └── _block_metrics(tree) → list[BlockMetric]
 │              └── _decision_weight(node) → int
 ├── comparer avec seuils → list[MetricResult]
 └── afficher tableau + exit(1) si violation
```

**Complexité cyclomatique — poids des nœuds AST :**

| Nœud | Incrément |
|---|---|
| `If`, `For`, `While`, `With` | +1 |
| `ExceptHandler` | +1 |
| `BoolOp(And/Or)` | +(nb_opérandes - 1) |
| `Match` | +1 par `case` |
| Base | 1 |

### 5.4 `security_deps.sh` — structure interne

```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p work
REQ="work/requirements_runtime.txt"

uv export --no-dev --no-hashes --format requirements-txt > "$REQ"

# Vérifie si le fichier contient des dépendances réelles
if ! grep -qE '^[a-zA-Z]' "$REQ"; then
    echo "Aucune dépendance runtime — audit ignoré."
    exit 0
fi

uv run pip-audit --strict --requirement "$REQ"
```

### 5.5 `publish.sh` — structure interne

```bash
#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:?Usage: publish.sh <build|check-dist|publish-test|publish>}"
DIST_DIR="work/dist"

cleanup() {
    find "$DIST_DIR" -not -name '.gitkeep' -delete 2>/dev/null || true
    rmdir "$DIST_DIR" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$DIST_DIR"

echo "=== Build ==="
uv build --out-dir "$DIST_DIR"

echo "=== Validation ==="
uv run twine check "$DIST_DIR"/*

case "$ACTION" in
    build|check-dist)
        echo "Action '$ACTION' terminée."
        ;;
    publish-test)
        echo "=== Publication TestPyPI ==="
        uv run twine upload --repository testpypi "$DIST_DIR"/*
        ;;
    publish)
        echo "=== Publication PyPI ==="
        uv run twine upload "$DIST_DIR"/*
        ;;
    *)
        echo "Action inconnue : $ACTION" >&2
        exit 1
        ;;
esac
```

---

## 6. Interface CLI

### 6.1 Définition Typer

```python
import typer
from rich.console import Console

app = typer.Typer(name="uvforge", help="uv overlay for Python package scaffolding.")
console = Console()

@app.command()
def init(
    project_name: Annotated[str | None, typer.Argument()] = None,
    python: Annotated[str, typer.Option(help="Python version")] = "3.12",
    no_git: Annotated[bool, typer.Option("--no-git")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None: ...

@app.command()
def check(
    fix: Annotated[bool, typer.Option("--fix")] = False,
) -> None: ...

@app.command()
def update(
    deps: Annotated[bool, typer.Option("--deps")] = False,
) -> None: ...
```

### 6.2 Point d'entrée `pyproject.toml`

```toml
[project.scripts]
uvforge = "uvforge.cli:app"
```

---

## 7. Flux d'exécution

### 7.1 `uvforge init mylib` — séquence nominale

```
CLI (cli.py)
  │
  ├── résoudre project_name = "mylib"
  ├── construire ProjectContext
  │
  └── init.run_init(ctx)
        │
        ├── uv_runner.check_uv_available()
        ├── scaffold.create_directories(ctx)
        │     └── src/mylib/, tests/, scripts/, work/, doc/
        ├── scaffold.ensure_gitkeep(work/)
        ├── renderer.render_template("pyproject.toml.tmpl") → scaffold.write_file()
        ├── renderer.render_template("Makefile.tmpl")       → scaffold.write_file()
        ├── renderer.render_template("gitignore.tmpl")      → scaffold.write_file(".gitignore")
        ├── renderer.render_template("README.md.tmpl")      → scaffold.write_file()
        ├── scaffold.write_file(".python-version", "3.12")
        ├── scaffold.write_file("src/mylib/__init__.py", "")
        ├── scaffold.write_file("src/mylib/py.typed", "")
        ├── scaffold.write_file("tests/__init__.py", "")
        ├── scaffold.write_file("tests/test_mylib.py", SMOKE_TEST_TEMPLATE)
        ├── scaffold.write_file("scripts/__init__.py", "")
        ├── scaffold.copy_script("templates/scripts/check.sh", "scripts/check.sh")
        ├── scaffold.copy_script("templates/scripts/check_docstrings.py", ...)
        ├── scaffold.copy_script("templates/scripts/code_metrics.py", ...)
        ├── scaffold.copy_script("templates/scripts/security_deps.sh", ...)
        ├── scaffold.copy_script("templates/scripts/publish.sh", ...)
        ├── uv_runner.uv_add_dev_deps(project_dir, DEV_DEPS)
        ├── uv_runner.uv_sync(project_dir)
        ├── uv_runner.git_init(project_dir)
        ├── uv_runner.git_add_all(project_dir)
        ├── uv_runner.git_commit(project_dir, "chore: uvforge init")
        └── console.print(résumé)
```

### 7.2 `uvforge check` — séquence nominale

```
CLI → check.run_check(cwd, fix=False)
  │
  ├── pour chaque vérification dans CHECKS
  │     └── fn(project_dir) → CheckResult
  │
  ├── afficher résultats PASS/FAIL (rich Table)
  │
  └── sys.exit(0 si tout PASS, 1 sinon)
```

---

## 8. Gestion des erreurs

### 8.1 Hiérarchie des exceptions uvforge

```python
class UvforgeError(Exception): ...
class UvNotFoundError(UvforgeError): ...
class ConflictError(UvforgeError): ...
class CommandError(UvforgeError):
    returncode: int
    stderr: str
class TemplateError(UvforgeError): ...
class InitError(UvforgeError): ...
```

### 8.2 Traitement dans la CLI

```python
try:
    init.run_init(ctx)
except UvNotFoundError:
    console.print("[red]Erreur:[/] uv non trouvé dans le PATH.")
    console.print("Installez uv : https://docs.astral.sh/uv/getting-started/installation/")
    raise typer.Exit(1)
except ConflictError:
    console.print("[red]Erreur:[/] Un pyproject.toml existe déjà. Utilisez --force.")
    raise typer.Exit(1)
except CommandError as e:
    console.print(f"[red]Erreur commande (code {e.returncode}):[/]\n{e.stderr}")
    raise typer.Exit(1)
```

---

## 9. Stratégie de test

### 9.1 Organisation des tests

```
tests/
├── unit/
│   ├── test_scaffold.py        # tests filesystem avec tmp_path
│   ├── test_renderer.py        # tests rendu templates
│   ├── test_uv_runner.py       # tests subprocess (mocké)
│   ├── test_init.py            # tests orchestration (mocks scaffold+renderer+uv)
│   ├── test_check.py           # tests audit
│   └── test_update.py          # tests update
├── scripts/
│   ├── test_check_docstrings.py   # tests check_docstrings.py avec fixtures AST
│   ├── test_code_metrics.py       # tests code_metrics.py avec fixtures de code
│   ├── test_publish_sh.py         # tests publish.sh via subprocess dans tmp_path
│   └── test_security_deps_sh.py   # tests security_deps.sh via subprocess
└── integration/
    └── test_full_init.py          # uvforge init → make check → 0
```

### 9.2 Fixtures partagées (`conftest.py`)

```python
@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    """Répertoire vide simulant un projet cible."""
    return tmp_path / "testproject"

@pytest.fixture
def minimal_project(tmp_path: Path) -> Path:
    """Projet uvforge complet minimal pour tester check/update."""
    # Appelle run_init avec un mock uv_runner
    ...
```

### 9.3 Tests des scripts — approche

**`test_check_docstrings.py`** : crée des fichiers Python synthétiques dans `tmp_path`, invoque `check_docstrings.py` via `subprocess.run`, vérifie le code de sortie et la présence de messages dans stdout.

```python
def test_private_function_without_docstring(tmp_path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "mod.py").write_text("def _helper(): pass\n")
    result = subprocess.run(
        ["python", str(SCRIPT_PATH)],
        cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "_helper" in result.stdout
```

**`test_publish_sh.py`** : crée un package Python minimal buildable dans `tmp_path`, exécute `publish.sh build`, vérifie que `work/dist/` est créé puis supprimé.

**`test_code_metrics.py`** : génère du code Python avec une complexité cyclomatique connue (ex. une fonction avec 5 `if` = complexité 6), vérifie que le script rapporte la bonne valeur.

### 9.4 Couverture des scripts shell

Les scripts shell ne peuvent pas être couverts par `pytest-cov`. La couverture est assurée par :
- Des tests paramétrés couvrant chaque branche conditionnelle (`ACTION=build`, `ACTION=publish`, fichier vide, etc.)
- Des tests de cas limites (répertoire `work/dist/` déjà présent, pas de dépendances runtime)

---

## 10. Décisions de conception

### 10.1 Pourquoi les scripts sont des fichiers statiques et non des templates

Les scripts (`check.sh`, `publish.sh`, etc.) sont copiés tels quels sans variables Jinja2. Justification : ils doivent pouvoir être modifiés par l'utilisateur après la génération, et leur logique ne dépend pas du nom du projet.

### 10.2 Pourquoi `importlib.resources` et non un chemin relatif

`importlib.resources` fonctionne correctement après installation via `uv tool install` (le package est dans un wheel), alors qu'un chemin relatif à `__file__` peut être incorrect dans certains contextes d'installation.

### 10.3 Pourquoi `subprocess` pour les appels uv/git

uv n'expose pas d'API Python publique. `subprocess` est le seul moyen fiable d'intégrer avec un binaire externe. L'encapsulation dans `uv_runner.py` isole ce couplage et facilite le mock dans les tests.

### 10.4 Pourquoi Typer et non Click

Typer génère les parseurs d'arguments depuis les annotations de type Python, ce qui évite la duplication entre les annotations mypy et la définition CLI. Typer supporte nativement l'autocomplétion shell. Il est utilisé en production par des outils de l'écosystème uv/ruff.

### 10.5 Séparation `scaffold.py` / `renderer.py` / `init.py`

- `scaffold.py` ne sait rien des templates — il manipule des `Path` et des `str`.
- `renderer.py` ne sait rien du filesystem — il retourne des `str`.
- `init.py` orchestre les deux, ce qui permet de tester chaque composant indépendamment.

### 10.6 `work/` : contenu ignoré par git, répertoire tracké

Le fichier `.gitkeep` est créé par uvforge et ajouté dans `.gitignore` avec l'exception `!work/.gitkeep`. Le contenu (`*.log`, `.coverage`, `dist/`, `requirements_runtime.txt`) est ignoré par la règle `work/*`. Ceci reproduit exactement le comportement de mkforge.
