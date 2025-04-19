# VPNGate IP Risk Checker

This program checks the risk scores for VPNGate server IPs using the ipdata.co API and adds the risk information to the VPNGate server data.

## Features

- Fetches VPNGate server list
- Checks each IP against ipdata.co for risk assessment
- Includes rate limiting to comply with API restrictions
- Saves results with original data in a new JSON file

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure your `.env` file contains the IPDATA_API_KEY:
```
IPDATA_API_KEY=your_api_key_here
```

## Usage

Simply run:
```bash
python check_vpn_risk.py
```

The program will:
1. Fetch the latest VPNGate server list
2. Check each IP for risk factors
3. Save the results in `vpngate_with_risk.json`

## Output Format

The program adds a `risk_data` field to each server entry with the following information:
- `is_threat`: Whether the IP is considered a threat
- `is_proxy`: Whether the IP is a known proxy
- `is_vpn`: Whether the IP is a known VPN
- `is_tor`: Whether the IP is a Tor exit node
- `is_datacenter`: Whether the IP is from a datacenter
- `risk_score`: Overall risk score (0-100) 