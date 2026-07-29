#!/usr/bin/env python3
"""Add or remove destinations tracked by the pricing automation.

Usage:
  python scripts/manage_destinations.py add "Nashville, TN" BNA --category suggested
  python scripts/manage_destinations.py add "Denver, CO" --category suggested   # code auto-looked-up via Amadeus
  python scripts/manage_destinations.py remove "Nashville, TN"
  python scripts/manage_destinations.py remove BNA
  python scripts/manage_destinations.py list
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

from amadeus_auth import BASE_URL, get_token

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "destinations.json"
AMADEUS_KEY = os.environ.get("AMADEUS_API_KEY")
AMADEUS_SECRET = os.environ.get("AMADEUS_API_SECRET")


def load_destinations():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_destinations(destinations):
    with open(DATA_FILE, "w") as f:
        json.dump(destinations, f, indent=2)
        f.write("\n")


def lookup_code(city_name):
    if not AMADEUS_KEY or not AMADEUS_SECRET:
        print(
            f"No IATA code given for '{city_name}' and no AMADEUS_API_KEY/SECRET set "
            "for automatic lookup. Provide a code manually, e.g.: "
            f"manage_destinations.py add \"{city_name}\" XXX",
            file=sys.stderr,
        )
        sys.exit(1)

    token = get_token(AMADEUS_KEY, AMADEUS_SECRET)
    r = requests.get(
        f"{BASE_URL}/v1/reference-data/locations",
        headers={"Authorization": f"Bearer {token}"},
        params={"keyword": city_name, "subType": "CITY,AIRPORT"},
        timeout=30,
    )
    r.raise_for_status()
    results = r.json().get("data", [])
    if not results:
        print(f"Could not find an IATA code for '{city_name}'. Please provide one manually.", file=sys.stderr)
        sys.exit(1)
    return results[0]["iataCode"]


def cmd_add(args):
    destinations = load_destinations()
    code = args.code.upper() if args.code else lookup_code(args.name)

    existing = next((d for d in destinations if d["code"] == code), None)
    if existing:
        print(f"'{code}' is already tracked as {existing['name']}.")
        return

    destinations.append({"name": args.name, "code": code, "category": args.category})
    save_destinations(destinations)
    print(f"Added {args.name} ({code}) as '{args.category}'.")


def cmd_remove(args):
    destinations = load_destinations()
    key = args.identifier.strip().lower()
    remaining = [d for d in destinations if d["name"].lower() != key and d["code"].lower() != key]

    if len(remaining) == len(destinations):
        print(f"No destination matching '{args.identifier}' found.")
        return

    save_destinations(remaining)
    print(f"Removed '{args.identifier}'.")


def cmd_list(args):
    for d in load_destinations():
        print(f"{d['name']} ({d['code']}) - {d['category']}")


def main():
    parser = argparse.ArgumentParser(description="Manage tracked travel destinations.")
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Add a new destination to track.")
    add_p.add_argument("name", help="Display name, e.g. 'Nashville, TN'")
    add_p.add_argument(
        "code",
        nargs="?",
        default=None,
        help="IATA airport/city code (auto-looked-up via Amadeus if omitted)",
    )
    add_p.add_argument("--category", default="suggested", choices=["suggested", "visited"])
    add_p.set_defaults(func=cmd_add)

    remove_p = sub.add_parser("remove", help="Remove a destination by name or IATA code.")
    remove_p.add_argument("identifier", help="Name or IATA code of the destination to remove")
    remove_p.set_defaults(func=cmd_remove)

    list_p = sub.add_parser("list", help="List all tracked destinations.")
    list_p.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
