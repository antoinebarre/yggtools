# SDD — Software Design Document

**Projet :** uvforge  
**Version :** 1.2  
**Date :** 2026-06-13  
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
├── suppressions.py      # scan des suppressions inline
├── report.py            # génération du rapport Markdown
└── templates/           # ressources statiques (MANIFEST)
    ├── scripts/
    │   ├── check.sh
    │   ├── check_docstrings.py
    │   ├── code_metrics.py
    │   ├── generate_report.py
    │   ├── security_deps.sh
    │   └── publish.sh
    ├── Makefile.tmpl
    ├── pyproject.toml.tmpl
    ├── gitignore.tmpl
    ├── README.md.tmpl
    ├── github_ci.yml.tmpl
    └── gitlab_ci.yml.tmpl
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

@dataclass(frozen=True)
class SuppressionItem:
    """Une annotation de suppression inline trouvée dans le code source."""
    file: str      # chemin relatif à project_root
    line: int      # numéro de ligne (1-indexed)
    kind: str      # "noqa" | "nosec" | "type: ignore" | "pragma: no cover"
    code: str      # code associé ("E501", "B603", …) ou "" si bare
    excerpt: str   # texte de la ligne (stripped)

@dataclass(frozen=True)
class FileChecksum:
    """Empreinte SHA-256 d'un fichier source audité."""
    path: str    # chemin relatif à project_root
    sha256: str  # hexdigest 64 caractères

@dataclass
class ReportData:
    """Données agrégées pour la génération du rapport de qualité."""
    project_name: str
    project_dir: Path
    uvforge_version: str
    generated_at: datetime
    check_results: list[CheckResult] = field(default_factory=list)
    checksums: list[FileChecksum] = field(default_factory=list)
    suppressions: list[SuppressionItem] = field(default_factory=list)
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

_write_ci_files(ctx)      [si pas ctx.no_git]
  ├── render_template("github_ci.yml.tmpl", ctx) → write ".github/workflows/ci.yml"
  └── render_template("gitlab_ci.yml.tmpl", ctx) → write ".gitlab-ci.yml"

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

### 3.8 `suppressions.py`

Scanne les fichiers Python d'un projet à la recherche d'annotations de suppression inline.

**Interface publique :**

```python
def scan_suppressions(src_dirs: list[Path], project_root: Path) -> list[SuppressionItem]:
    """Parcourt les répertoires donnés et retourne toutes les suppressions trouvées,
    triées par fichier puis par numéro de ligne."""
```

**Fonctions internes :**

```python
def _scan_file(path: Path, project_root: Path) -> list[SuppressionItem]:
    """Scanne un fichier individuel. Retourne [] si le fichier est illisible."""

def _extract_suppressions(rel_path: str, lineno: int, text: str) -> list[SuppressionItem]:
    """Extrait toutes les suppressions d'une ligne. Déduplique par (kind, code)."""
```

**Patterns reconnus :**

| Kind | Syntaxe |
|---|---|
| `noqa` | `# noqa: E501` ou `# noqa` |
| `nosec` | `# nosec B603` ou `# nosec` |
| `type: ignore` | `# type: ignore[attr-defined]` ou `# type: ignore` |
| `pragma: no cover` | `# pragma: no cover` |

**Déduplication :** la paire `(kind, code)` est dédupliquée par ligne via un `set` d'émis. Les répertoires inexistants sont silencieusement ignorés.

### 3.9 `report.py`

Construit et écrit le rapport Markdown de qualité à partir d'un `ReportData`.

**Interface publique :**

```python
def build_report_data(project_dir: Path) -> ReportData:
    """Collecte toutes les données (résultats check, checksums, suppressions)."""

def collect_checksums(project_dir: Path) -> list[FileChecksum]:
    """Retourne les checksums SHA-256 de tous les .py dans src/, triés."""

def render_report(data: ReportData) -> Report:
    """Construit et retourne un objet mkforge.Report prêt à être rendu."""

def save_report(data: ReportData, output: Path) -> None:
    """Écrit le rapport Markdown à output (crée les répertoires parents si nécessaire)."""
```

**Fonctions internes (chapitres) :**

```python
def _summary_chapter(data: ReportData) -> Chapter: ...
def _check_results_chapter(results: list[CheckResult]) -> Chapter: ...
def _checksums_chapter(checksums: list[FileChecksum]) -> Chapter: ...
def _suppressions_chapter(suppressions: list[SuppressionItem]) -> Chapter: ...
def _sha256(path: Path) -> str: ...
```

**Structure du rapport généré :**

```
# Quality Report — <project_name>

## 1. Summary
  Tableau : Project, Generated at, uvforge version, Checks passed, Checks failed

## 2. Check Results
  Tableau : Check | Status | Detail

## 3. File Checksums
  Tableau : File | SHA-256

## 4. Security Suppressions
  Total : N suppression(s) found
  Pour chaque fichier : section avec tableau Line | Kind | Code | Excerpt
```

---

## 4. Templates et ressources embarquées

### 4.1 Déclaration dans `pyproject.toml`

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/uvforge"]
```

Hatch inclut automatiquement `src/uvforge/templates/` dans le wheel car `templates/` est un sous-package de `uvforge` (présence de `__init__.py`). L'utilisation de `force-include` est proscrite : elle crée un répertoire `uvforge/` à la racine de `site-packages` sans `__init__.py`, ce qui provoque une collision de namespace package masquant le vrai package installé.

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

Le script exécute 9 étapes via la fonction `run()` qui :
1. Redirige stdout/stderr vers `work/<nom>.log`
2. Écrit `0` ou `1` dans `work/<nom>.exit` (fichier sentinelle lu par `generate_report.py`)
3. Affiche PASS/FAIL coloré avec un résumé extrait du log

Après le résumé du pipeline, il appelle `generate_report.py` :

```bash
REPORT_OUTPUT="${REPORT_OUTPUT:-work/report.md}"

run() {
    local name="$1"; shift
    local log="work/${name}.log"
    local exit_file="work/${name}.exit"
    if "$@" > "$log" 2>&1; then
        echo "0" > "$exit_file"
        ...PASS...
    else
        echo "1" > "$exit_file"
        ...FAIL...
    fi
}

# Après les 9 étapes :
uv run python scripts/generate_report.py --output "$REPORT_OUTPUT" \
    && printf "Report: %s\n" "$REPORT_OUTPUT" \
    || printf "Warning: report generation failed\n"

cleanup  # supprime work/*.log, work/*.exit — mais PAS work/report.md
exit "$FAIL"
```

**cleanup** exclut `report.md` via `! -name "report.md"` pour que le rapport survive au nettoyage.

### 5.2 `generate_report.py` — structure interne

Script autonome (sans import de `uvforge`) embarqué dans `templates/scripts/` et copié dans `scripts/` des projets générés.

**Algorithme principal :**

```
main(output: Path)
 ├── _read_check_results(project_root)
 │    └── pour chaque step in PIPELINE_STEPS
 │         ├── lire work/<step>.exit → passed (0=True, 1=False)
 │         └── lire work/<step>.log → detail (dernière ligne pertinente)
 ├── _collect_checksums(project_root)
 │    └── sha256 de chaque .py dans src/
 ├── _scan_suppressions(project_root)
 │    └── scan de src/ + tests/ + scripts/
 ├── _build_report(project_name, results, checksums, suppressions)
 │    └── mkforge.Report avec 4 chapitres
 └── output.write_text(report.render())
```

**Contraintes de conception :**
- `importlib.metadata` importé au niveau module (pas dans une fonction) pour respecter `PLC0415`.
- `_uvforge_version()` attrape `importlib.metadata.PackageNotFoundError` explicitement (pas `Exception`).
- Le scan de suppressions est découpé en `_scan_file_suppressions()` + `_extract_line_suppressions()` pour maintenir CC ≤ 10.
- `PIPELINE_STEPS` liste les 9 noms dans l'ordre d'exécution de `check.sh`.

### 5.3 `check_docstrings.py` — structure interne

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
        ├── renderer.render_template("github_ci.yml.tmpl") → scaffold.write_file(".github/workflows/ci.yml")
        ├── renderer.render_template("gitlab_ci.yml.tmpl") → scaffold.write_file(".gitlab-ci.yml")
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
│   ├── test_update.py          # tests update
│   ├── test_suppressions.py    # tests scan suppressions (tous types, dédup, erreurs)
│   └── test_report.py          # tests génération rapport (chapitres, checksums, écriture)
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

### 10.7 Pourquoi `generate_report.py` est un script autonome sans import de `uvforge`

Le script est copié dans `scripts/` du projet cible et exécuté par `uv run` dans cet environnement, qui n'a pas `uvforge` installé. Un import de `uvforge` ferait échouer l'exécution dans tout projet généré. La duplication de la logique de scan de suppressions entre `uvforge.suppressions` et `generate_report.py` est volontaire et documentée.

### 10.8 Pourquoi `mkforge` et non `string.Template` pour le rapport

`mkforge` fournit un DSL Python orienté domaine (`Report`, `Chapter`, `Section`, `Table`, `Paragraph`) avec gestion automatique de la table des matières et des niveaux de titres. `string.Template` produirait du code de concaténation fragile et difficile à tester indépendamment. La dépendance est justifiée car `mkforge` est la bibliothèque de référence de génération de rapports Markdown pour ce projet.

### 10.9 Pourquoi `REPORT_OUTPUT` et non une option CLI de `uvforge`

Le rapport est produit par `check.sh`, pas par `uvforge`. L'utilisateur peut intégrer `check.sh` dans des pipelines CI qui définissent déjà `REPORT_OUTPUT` comme variable d'environnement. Une option CLI supplémentaire sur `uvforge` aurait couplé la génération du rapport à la CLI alors que le workflow principal passe par `make check → check.sh`.

### 10.10 Pourquoi les fichiers sentinelles `work/<nom>.exit`

`generate_report.py` doit reconstruire les résultats du pipeline après que `check.sh` ait terminé. Lire les codes de sortie depuis les fichiers `work/<nom>.exit` est plus robuste que parser les logs (format non stable). Les fichiers sentinelles sont une interface contractuelle explicite entre `check.sh` et `generate_report.py`.

### 10.11 Pourquoi les workflows CI sont des templates Jinja2 et non des fichiers statiques

Contrairement aux scripts de qualité (copiés tels quels), les workflows CI doivent être paramétrés par la version Python cible du projet (`{{ python_version }}`). Un fichier statique forcerait toujours la même version, ou imposerait à l'utilisateur de l'éditer manuellement. La variable `{{ python_version }}` est la seule variable Jinja2 utilisée dans ces templates ; la version 3.13 est fixe car c'est la version stable la plus récente au moment de la génération.

### 10.12 Pourquoi les workflows CI sont omis avec `--no-git`

Les workflows GitHub Actions et GitLab CI n'ont de sens que dans un dépôt git avec un remote configuré. Générer ces fichiers sans dépôt git crée une confusion sans valeur ajoutée. L'option `--no-git` signale explicitement l'absence d'intention de versionnement — omettre les workflows CI est la conséquence logique.
