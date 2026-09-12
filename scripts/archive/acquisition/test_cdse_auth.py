import os
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

client_id = os.getenv("CDSE_CLIENT_ID")
client_secret = os.getenv("CDSE_CLIENT_SECRET")

if not client_id or not client_secret:
    raise RuntimeError(
        "CDSE_CLIENT_ID or CDSE_CLIENT_SECRET is missing from .env"
    )


TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)

response = requests.post(
    TOKEN_URL,
    data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    },
    timeout=30,
)

response.raise_for_status()

token_data = response.json()

access_token = token_data.get("access_token")
expires_in = token_data.get("expires_in")

if not access_token:
    raise RuntimeError("Authentication succeeded but no access token was returned.")

print("=" * 60)
print("COPERNICUS DATA SPACE AUTH TEST")
print("=" * 60)
print("Authentication : SUCCESS")
print(f"Token received : YES")
print(f"Expires in     : {expires_in} seconds")
print("=" * 60)