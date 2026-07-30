"""Shared Amadeus OAuth helper used by fetch_pricing.py and manage_destinations.py."""
import os

import requests

BASE_URL = os.environ.get("AMADEUS_BASE_URL", "https://test.api.amadeus.com")


def get_token(api_key, api_secret):
    resp = requests.post(
        f"{BASE_URL}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": api_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]
