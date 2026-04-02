#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

rm -rf ./tree-sitter-java
git clone --depth 1 https://github.com/tree-sitter/tree-sitter-java.git
(cd ./tree-sitter-java && make)

rm -rf ./tree-sitter-kotlin
git clone --depth 1 https://github.com/fwcd/tree-sitter-kotlin.git
(cd ./tree-sitter-kotlin && make)

rm -rf ./tree-sitter-python
git clone --depth 1 https://github.com/tree-sitter/tree-sitter-python.git
(cd ./tree-sitter-python && make)
