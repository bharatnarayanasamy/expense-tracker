#!/usr/bin/env bash
# Export macOS trust store to a PEM file for pip (fixes corporate MITM / AutoDesk root CA).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/scripts/macOS-keychain-ca-bundle.pem"

: > "$OUT"
append_chain() {
  local label="$1"
  shift
  if security find-certificate -a -p "$@" >> "$OUT" 2>/dev/null; then
    echo "  + $label"
  fi
}

append_chain "System roots" /System/Library/Keychains/SystemRootCertificates.keychain
append_chain "System keychain" /Library/Keychains/System.keychain
if [[ -f "$HOME/Library/Keychains/login.keychain-db" ]]; then
  append_chain "Login keychain" "$HOME/Library/Keychains/login.keychain-db"
fi

# Explicit search for Autodesk corporate roots (if installed in Keychain)
for name in "AutoDesk WW HQ Root CA" "Autodesk WW HQ Root CA"; do
  security find-certificate -c "$name" -p >> "$OUT" 2>/dev/null || true
done

bytes="$(wc -c < "$OUT" | tr -d ' ')"
if [[ "$bytes" -lt 1000 ]]; then
  echo "WARNING: PEM bundle looks too small ($bytes bytes). Add your corporate root CA to Keychain." >&2
fi

echo "Wrote $OUT ($bytes bytes)"
echo "Next: ./scripts/bootstrap.sh"
