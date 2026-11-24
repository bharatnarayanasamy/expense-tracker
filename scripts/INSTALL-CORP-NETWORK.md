# Installing on a corporate network (Autodesk / SSL / 503)

You **do not** need:

- `pip install -e .`
- the `expense-tracker` shell command

Use **`./run.sh serve`** after dependencies are installed.

## Standard install

```bash
cd /Users/narayab/Personal/expense-tracker
python3 -m venv .venv
source .venv/bin/activate
chmod +x scripts/*.sh run.sh
./scripts/bootstrap.sh
./run.sh serve
```

`bootstrap.sh` exports macOS Keychain CAs (if needed), sets `PIP_CERT` / `--cert`, and installs `requirements.txt` only.

## Error: `AutoDesk WW HQ Root CA` is not trusted

1. Open **Keychain Access** → search **AutoDesk WW HQ Root CA**.
2. If missing, install the cert from IT / internal docs. Set trust to **Always Trust** (System keychain if prompted).
3. Re-export and bootstrap:

```bash
./scripts/export-macos-certs.sh
./scripts/bootstrap.sh
```

Manual env (same as bootstrap uses):

```bash
export PIP_CERT="$PWD/scripts/macOS-keychain-ca-bundle.pem"
export REQUESTS_CA_BUNDLE="$PIP_CERT"
export SSL_CERT_FILE="$PIP_CERT"
python -m pip install --cert "$PIP_CERT" -r requirements.txt
```

## Error: `503` from files.pythonhosted.org

PyPI CDN is unreachable or rate-limited through the proxy.

- Wait and retry `./scripts/bootstrap.sh`
- Disconnect VPN / try home Wi‑Fi
- Use company Artifactory/DevPI:

```bash
export PIP_INDEX_URL="https://YOUR-INTERNAL-MIRROR/simple"
./scripts/bootstrap.sh
```

## Error: `Cannot import setuptools.build_meta`

Caused by `pip install -e .`. **Stop using editable install.** Use `./scripts/bootstrap.sh` instead.

## Python version

If Python 3.14 has wheel issues:

```bash
rm -rf .venv
PYTHON=python3.12 ./scripts/bootstrap.sh
```

## Run without global CLI

```bash
source .venv/bin/activate
./run.sh serve              # web UI
./run.sh import ~/Downloads/statement.pdf
./run.sh stats --month 2026-01
```

Equivalent: `python -m expense_tracker serve` with `PYTHONPATH` set ( `./run.sh` does this).
