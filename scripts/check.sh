#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-local}"

G='\033[32m'
R='\033[31m'
B='\033[1m'
N='\033[0m'
SEP="────────────────────────────────────────────────────────────────────────────────"

PASS=0
FAIL=0
FAILED_NAMES=()

cleanup() {
    mkdir -p work
    find work -mindepth 1 ! -name .gitkeep -exec rm -rf {} + 2>/dev/null || true
}

count_matches() {
    local pattern="$1"
    local file="$2"
    grep "$pattern" "$file" 2>/dev/null | wc -l | tr -d " "
}

detail_for() {
    local name="$1"
    local log="work/${name}.log"
    [[ -f "$log" ]] || { echo ""; return; }
    case "$name" in
        format)
            local n
            n=$(count_matches "reformatted" "$log")
            echo "${n} file(s) reformatted"
            ;;
        ruff)
            local n
            n=$(count_matches " error" "$log")
            echo "${n} error(s)"
            ;;
        flake8)
            tail -1 "$log" 2>/dev/null || echo ""
            ;;
        docstrings)
            local n
            n=$(count_matches ":" "$log")
            echo "${n} issue(s)"
            ;;
        typecheck)
            grep -E "^(Success|Found)" "$log" 2>/dev/null | tail -1 \
                || echo "ok"
            ;;
        metrics)
            head -1 "$log" 2>/dev/null || echo ""
            ;;
        security-code)
            local n
            n=$(count_matches "^>> Issue:" "$log")
            echo "${n} issue(s)"
            ;;
        security-deps)
            tail -1 "$log" 2>/dev/null || echo ""
            ;;
        tests)
            grep -E "passed|failed|error" "$log" 2>/dev/null | tail -1 \
                || echo ""
            ;;
        *)
            echo ""
            ;;
    esac
}

run() {
    local name="$1"
    shift
    local log="work/${name}.log"
    if "$@" > "$log" 2>&1; then
        local detail
        detail=$(detail_for "$name")
        printf "${G}✓ PASS${N}  %-20s  %s\n" "$name" "$detail"
        PASS=$((PASS + 1))
    else
        local detail
        detail=$(detail_for "$name")
        printf "${R}✗ FAIL${N}  %-20s  %s\n" "$name" "$detail"
        FAIL=$((FAIL + 1))
        FAILED_NAMES+=("$name")
    fi
}

print_failures() {
    for name in "${FAILED_NAMES[@]}"; do
        local log="work/${name}.log"
        echo ""
        printf "${B}%s${N}\n" "$SEP"
        printf "${R}Detail: %s${N}\n" "$name"
        printf "${B}%s${N}\n" "$SEP"
        [[ -f "$log" ]] && cat "$log" || echo "(no log)"
    done
}

cleanup

echo ""
printf "${B}uvforge quality pipeline — mode: %s${N}\n" "$MODE"
printf "${B}%s${N}\n" "$SEP"
printf "%-7s  %-20s  %s\n" "Status" "Check" "Detail"
printf "${B}%s${N}\n" "$SEP"

if [[ "$MODE" == "--ci" ]]; then
    run "format"        uv run ruff format --check src tests scripts
else
    run "format"        uv run ruff format src tests scripts
fi

run "ruff"              uv run ruff check src tests scripts
run "flake8"            uv run flake8 src tests scripts
run "docstrings"        uv run python scripts/check_docstrings.py
run "typecheck"         uv run mypy src tests scripts
run "metrics"           uv run python scripts/code_metrics.py
run "security-code"     uv run bandit -r src -x tests,work -q
run "security-deps"     bash scripts/security_deps.sh
run "tests"             uv run pytest

printf "${B}%s${N}\n" "$SEP"
printf "Result: ${G}%d passed${N}  ${R}%d failed${N}\n" "$PASS" "$FAIL"

if [[ "${#FAILED_NAMES[@]}" -gt 0 ]]; then
    print_failures
fi

cleanup
exit "$FAIL"
