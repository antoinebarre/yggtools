#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:?missing publish action}"

cleanup() {
    mkdir -p work
    find work -mindepth 1 ! -name .gitkeep -exec rm -rf {} +
}

cleanup
trap cleanup EXIT
mkdir -p work/dist

uv build --out-dir work/dist
uv run twine check work/dist/*

case "$ACTION" in
    build | check-dist)
        ;;
    publish-test)
        uv run twine upload --repository testpypi work/dist/*
        ;;
    publish)
        uv run twine upload work/dist/*
        ;;
    *)
        echo "Unknown publish action: $ACTION" >&2
        exit 2
        ;;
esac
