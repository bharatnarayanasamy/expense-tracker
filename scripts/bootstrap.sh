#!/usr/bin/env bash
# Install runtime deps into .venv. Does NOT use pip install -e .
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

BUNDLE_PATH="$ROOT/scripts/macOS-keychain-ca-bundle.pem"
CERT_BUNDLE="${PIP_CERT:-${REQUESTS_CA_BUNDLE:-}}"

if [[ -z "${CERT_BUNDLE}" && -f "$BUNDLE_PATH" && -s "$BUNDLE_PATH" ]]; then
  CERT_BUNDLE="$BUNDLE_PATH"
fi

if [[ -z "${CERT_BUNDLE}" || ! -s "${CERT_BUNDLE}" ]]; then
  echo "==> Exporting macOS trust store to PEM (includes corporate roots if in Keychain)..."
  "$ROOT/scripts/export-macos-certs.sh"
  CERT_BUNDLE="$BUNDLE_PATH"
fi

export PIP_CERT="$CERT_BUNDLE"
export REQUESTS_CA_BUNDLE="$CERT_BUNDLE"
export SSL_CERT_FILE="$CERT_BUNDLE"

PIP_ARGS=(
  --retries 15
  --timeout 120
  --cert "$CERT_BUNDLE"
)
if [[ -n "${PIP_INDEX_URL:-}" ]]; then
  PIP_ARGS+=(--index-url "$PIP_INDEX_URL")
  echo "==> Using PIP_INDEX_URL=$PIP_INDEX_URL"
fi

echo "==> Using CA bundle: $CERT_BUNDLE"

echo "==> Ensuring pip (offline, bundled with Python)..."
python -m ensurepip --upgrade 2>/dev/null || python -m ensurepip --default-pip || true

if [[ "${UPGRADE_PIP:-0}" == "1" ]]; then
  echo "==> Upgrading pip (optional)..."
  python -m pip install "${PIP_ARGS[@]}" --upgrade pip || echo "    (pip upgrade skipped — continuing)"
else
  echo "==> Skipping pip upgrade (set UPGRADE_PIP=1 to force)."
fi

install_requirements() {
  python -m pip install "${PIP_ARGS[@]}" -r requirements.txt
}

echo "==> Installing dependencies from requirements.txt..."
if ! install_requirements; then
  echo ""
  echo "Install failed. Common fixes on Autodesk/corporate networks:"
  echo "  1. Trust AutoDesk WW HQ Root CA in Keychain Access (System), then re-run:"
  echo "       ./scripts/export-macos-certs.sh && ./scripts/bootstrap.sh"
  echo "  2. Retry off VPN or on a personal network (503 from files.pythonhosted.org)."
  echo "  3. Use internal PyPI: export PIP_INDEX_URL=https://your-artifactory/simple"
  echo "  4. Recreate venv with Python 3.12: rm -rf .venv && PYTHON=python3.12 ./scripts/bootstrap.sh"
  echo "  See scripts/INSTALL-CORP-NETWORK.md"
  exit 1
fi

python -c "import fastapi, typer, pdfplumber, yaml, openpyxl, httpx; print('All runtime imports OK')"

echo ""
echo "Start the app (no expense-tracker CLI needed):"
echo "  cd $ROOT && source .venv/bin/activate && ./run.sh serve"
