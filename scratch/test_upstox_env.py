import json
import os
import urllib.request
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip("'\"")

token = os.getenv("UPSTOX_ACCESS_TOKEN")
print("Token present:", bool(token))

url = "https://api.upstox.com/v2/market-quote/quotes?instrument_key=NSE_EQ%7CINE002A01018,NSE_EQ%7CINE040A01034"
headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {token}",
    "User-Agent": "QuantOS/1.0",
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("Upstox API Response Status:", data.get("status"))
        if "data" in data:
            for k, v in data["data"].items():
                print(
                    "  Instrument:",
                    k,
                    "| Last Price: Rs",
                    v.get("last_price"),
                    "| OHLC:",
                    v.get("ohlc"),
                )
except Exception as e:
    print("Upstox API Error:", e)
