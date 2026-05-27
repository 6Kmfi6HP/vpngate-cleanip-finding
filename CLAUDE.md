# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a small Python project that fetches VPNGate server data, enriches each server IP with local MaxMind GeoLite2 Country, City, and ASN databases, and writes two generated outputs:

- `vpngate_with_risk.json`: the VPNGate payload with per-server `maxmind` records.
- `mihomo_openvpn.yaml`: a mihomo `proxies` list generated from VPNGate OpenVPN configs.

The main implementation is in `check_vpn_risk.py`; tests live in `tests/test_check_vpn_risk.py`.

## Common commands

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Download the local MaxMind databases required by the main script:

```bash
mkdir -p maxmind
curl -fsSL "https://6kmfi6hp.github.io/maxmind/GeoLite2-Country.mmdb" -o maxmind/GeoLite2-Country.mmdb
curl -fsSL "https://6kmfi6hp.github.io/maxmind/GeoLite2-City.mmdb" -o maxmind/GeoLite2-City.mmdb
curl -fsSL "https://6kmfi6hp.github.io/maxmind/GeoLite2-ASN.mmdb" -o maxmind/GeoLite2-ASN.mmdb
```

Run the data generation script:

```bash
python check_vpn_risk.py
```

Run the full test suite:

```bash
python -m pytest -q
```

Run a single test:

```bash
python -m pytest tests/test_check_vpn_risk.py::test_build_mihomo_openvpn_config_decodes_vpngate_servers -q
```

There is no configured build step or lint command in this repository.

## Runtime configuration

`check_vpn_risk.py` reads environment variables via `python-dotenv`. Useful overrides include:

- `VPNGATE_API_URL`: source JSON URL for VPNGate data.
- `MAXMIND_DB_DIR`, `MAXMIND_COUNTRY_DB`, `MAXMIND_CITY_DB`, `MAXMIND_ASN_DB`: locations of local `.mmdb` files.
- `RETRY_TOTAL`, `RETRY_BACKOFF_FACTOR`, `REQUEST_TIMEOUT`: HTTP retry and timeout settings.
- `OUTPUT_FILE`, `MIHOMO_OUTPUT_FILE`: output paths for generated JSON and YAML.

The default MaxMind directory is `maxmind/`, which is gitignored along with `*.mmdb`.

## Architecture notes

`check_vpn_risk.py` has two main pipelines that share the fetched VPNGate payload:

1. MaxMind enrichment:
   - `fetch_vpngate_data()` downloads and validates that the response contains `data.servers`.
   - `main()` opens GeoLite2 Country, City, and ASN readers with `ExitStack`.
   - `annotate_servers_with_maxmind()` mutates each server in place, removes stale `ipdata` and `maxmind`, skips entries without `ip`, and attaches a fresh `maxmind` record when lookup data exists.
   - `build_maxmind_record()` compacts supported GeoIP fields only: country, registered country, continent, city, subdivision, location, postal, and ASN. MaxMind GeoLite2 does not produce VPN/proxy risk fields.

2. mihomo OpenVPN generation:
   - `decode_openvpn_config()` decodes `openvpn_configdata_base64` using strict base64 validation.
   - `parse_openvpn_config()` extracts `remote`, `proto`, `dev`, `cipher`, `auth`, and certificate/key blocks from the OpenVPN profile.
   - `build_mihomo_openvpn_proxy()` skips invalid or incomplete OpenVPN configs and defaults `tls-crypt` to an empty string when missing because mihomo expects the field.
   - `build_mihomo_proxy_name()` builds names from country ISO, ASN number, and the server `name`/`hostname`/`ip` fallback; it intentionally excludes ASN organization names.
   - `render_mihomo_yaml()` is a custom YAML renderer that quotes plain strings and emits multiline certificate values as block scalars.

Both generated files are written atomically through temporary files and `os.replace()`.

## Tests and CI

Unit tests avoid network and real MaxMind databases by using fake reader objects and in-memory VPNGate payloads. Most behavior is covered through pure functions in `check_vpn_risk.py`, so prefer adding tests at that level when changing parsing, enrichment, or rendering logic.

`.github/workflows/update-vpngate-maxmind.yml` runs daily and on manual dispatch. It installs dependencies, downloads the three MaxMind databases, runs `python -m pytest -q`, runs `python check_vpn_risk.py`, uploads generated artifacts, and commits `vpngate_with_risk.json` plus `mihomo_openvpn.yaml` only when they changed.

`auto_update.sh` runs `check_vpn_risk.py`, stages the two generated output files, commits if they changed, and pushes. Treat it as a publishing helper rather than a normal test command.
