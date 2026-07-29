#!/usr/bin/env python3
"""Fetch flight + hotel pricing from Chicago (ORD) to each tracked destination.

Uses the Amadeus self-service API (https://developers.amadeus.com).
Requires AMADEUS_API_KEY and AMADEUS_API_SECRET in the environment.
Writes results to PRICING.md in the repo root.
"""
import datetime
import json
import os
import sys
import time
from pathlib import Path

import requests

from amadeus_auth import BASE_URL, get_token

AMADEUS_KEY = os.environ.get("AMADEUS_API_KEY")
AMADEUS_SECRET = os.environ.get("AMADEUS_API_SECRET")

ORIGIN = "ORD"

DESTINATIONS_FILE = Path(__file__).resolve().parent.parent / "data" / "destinations.json"


def load_destinations():
    with open(DESTINATIONS_FILE) as f:
        return json.load(f)


def next_friday_weeks_out(weeks):
    d = datetime.date.today() + datetime.timedelta(weeks=weeks)
    days_ahead = (4 - d.weekday()) % 7  # Friday = 4
    return d + datetime.timedelta(days=days_ahead)


def get_flight_price(token, destination_code, depart_date, return_date):
    r = requests.get(
        f"{BASE_URL}/v2/shopping/flight-offers",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "originLocationCode": ORIGIN,
            "destinationLocationCode": destination_code,
            "departureDate": depart_date,
            "returnDate": return_date,
            "adults": 1,
            "currencyCode": "USD",
            "max": 5,
        },
        timeout=30,
    )
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    data = r.json().get("data", [])
    if not data:
        return None, "no offers"
    prices = [float(o["price"]["total"]) for o in data]
    return min(prices), None


def get_hotel_price(token, city_code, checkin, checkout):
    r = requests.get(
        f"{BASE_URL}/v1/reference-data/locations/hotels/by-city",
        headers={"Authorization": f"Bearer {token}"},
        params={"cityCode": city_code},
        timeout=30,
    )
    if r.status_code != 200:
        return None, f"HTTP {r.status_code} (hotel list)"
    hotel_ids = [h["hotelId"] for h in r.json().get("data", [])[:20] if "hotelId" in h]
    if not hotel_ids:
        return None, "no hotels found"

    r2 = requests.get(
        f"{BASE_URL}/v3/shopping/hotel-offers",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "hotelIds": ",".join(hotel_ids),
            "checkInDate": checkin,
            "checkOutDate": checkout,
            "adults": 1,
            "currency": "USD",
        },
        timeout=30,
    )
    if r2.status_code != 200:
        return None, f"HTTP {r2.status_code} (hotel offers)"
    prices = []
    for hotel in r2.json().get("data", []):
        for offer in hotel.get("offers", []):
            try:
                prices.append(float(offer["price"]["total"]))
            except (KeyError, ValueError):
                continue
    if not prices:
        return None, "no offers"
    return min(prices), None


def write_report(rows, depart, ret):
    lines = [
        "# Live Pricing: Chicago (ORD) to Destinations",
        "",
        f"_Last updated: {datetime.datetime.utcnow().isoformat()}Z_",
        f"_Sample trip window: {depart.isoformat()} to {ret.isoformat()} (round trip, 1 adult)_",
        "",
        "| Destination | Category | Round-trip Flight (ORD) | Hotel / night |",
        "|---|---|---|---|",
    ]
    for r in rows:
        flight = f"${r['flight_price']:.0f}" if r["flight_price"] else f"N/A ({r['flight_note']})"
        hotel = (
            f"${r['hotel_price_per_night']:.0f}"
            if r["hotel_price_per_night"]
            else f"N/A ({r['hotel_note']})"
        )
        lines.append(f"| {r['name']} ({r['code']}) | {r['category']} | {flight} | {hotel} |")

    lines.append("")
    lines.append(
        "_Pricing pulled from the Amadeus self-service API. On the free/test tier, "
        "availability and prices can be limited or approximate compared to production "
        "booking sites (Google Flights, Kayak, etc.) — treat as directional, not a "
        "guaranteed bookable price._"
    )

    with open("PRICING.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    if not AMADEUS_KEY or not AMADEUS_SECRET:
        print("Missing AMADEUS_API_KEY / AMADEUS_API_SECRET", file=sys.stderr)
        sys.exit(1)

    token = get_token(AMADEUS_KEY, AMADEUS_SECRET)

    depart = next_friday_weeks_out(5)
    ret = depart + datetime.timedelta(days=2)

    rows = []
    for dest in load_destinations():
        name, code, category = dest["name"], dest["code"], dest["category"]
        flight_price, flight_note = get_flight_price(token, code, depart.isoformat(), ret.isoformat())
        time.sleep(0.3)
        hotel_price, hotel_note = get_hotel_price(token, code, depart.isoformat(), ret.isoformat())
        time.sleep(0.3)
        rows.append(
            {
                "name": name,
                "code": code,
                "category": category,
                "flight_price": flight_price,
                "flight_note": flight_note,
                "hotel_price_per_night": hotel_price,
                "hotel_note": hotel_note,
            }
        )

    write_report(rows, depart, ret)


if __name__ == "__main__":
    main()
