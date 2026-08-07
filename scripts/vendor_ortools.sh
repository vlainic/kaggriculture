#!/usr/bin/env bash
# Download cp311 manylinux OR-Tools wheels and unpack into vendor/ for Kaggle sim.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WHEELS="$ROOT/vendor_wheels"
VENDOR="$ROOT/vendor"

mkdir -p "$WHEELS" "$VENDOR"

echo "==> Downloading ortools + deps (cp311, manylinux2014_x86_64)"
pip download ortools \
  --only-binary=:all: \
  --python-version 311 \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --abi cp311 \
  -d "$WHEELS"

echo "==> Unpacking wheels into vendor/"
# Wipe previous unpack (keep wheels cache)
find "$VENDOR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

for whl in "$WHEELS"/*.whl; do
  echo "  unzip $(basename "$whl")"
  unzip -qo "$whl" -d "$VENDOR"
done

# Drop wheel metadata only — keep importable packages
rm -rf "$VENDOR"/*.dist-info "$VENDOR"/*.data 2>/dev/null || true
find "$VENDOR" -type d -name '*.dist-info' -exec rm -rf {} + 2>/dev/null || true
find "$VENDOR" -type d -name '*.data' -exec rm -rf {} + 2>/dev/null || true

echo "==> vendor/ top-level:"
ls -la "$VENDOR" | head -40

echo "==> Import check (may use system libs for .so; path-only check):"
PYTHONPATH="$VENDOR" python3 -c "import ortools; print('ortools', ortools.__file__)" || true

echo "Done. vendor/ ready for packaging into submission.tar.gz"
