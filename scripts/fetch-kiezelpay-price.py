#!/usr/bin/env python3
"""Fetch live price/trial data from the KiezelPay merchant API.

KiezelPay is the in-app payment provider for every app in this repo. The
Garmin store API always reports these apps as free with no trial (see
fetch-garmin-app.py) - that field is a store artefact, not the truth. Real
price and trial length only exist in the developer's KiezelPay account, which
this script reads.

Usage:
    scripts/fetch-kiezelpay-price.py --list
    scripts/fetch-kiezelpay-price.py <productId> [--compare apps/<page>.html]

Options:
    --list           dump every product in the account (id, name, price) -
                     use this once to find a new app's productId, then save
                     it as "kiezelpayProductId" in apps-registry.json
    --compare PATH   diff the live price/trial against an existing app page

The API key is read from .env in the repo root (a line "API_KEY=..."), which
is gitignored. Get your own key at https://kiezelpay.com/account/api.

Rate limit: 20 requests/minute per key (KiezelPay enforces this; the error
message is self-explanatory). This script makes one request per run - pace
multiple sequential runs (a few seconds apart) if updating many apps in one
sitting.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://kiezelpay.com/api/merchant"
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"

# Below this many days, the site phrases the trial in hours (24/48/72 hours);
# at or above it, in days (5 days, 7 days). This matches every trial length
# already live on the site - there is no example of a 4-day trial to confirm
# the exact boundary, but this reproduces every existing page's phrasing.
HOURS_PHRASING_MAX_DAYS = 3


def read_api_key():
    if not ENV_FILE.exists():
        sys.exit(f"error: {ENV_FILE} not found - it must contain a line 'API_KEY=...'")
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit(f"error: no API_KEY= line in {ENV_FILE}")


def get(endpoint, key, **params):
    query = urllib.parse.urlencode({"key": key, **params})
    url = f"{API}/{endpoint}?{query}"
    # Cloudflare in front of kiezelpay.com 403s the default "Python-urllib/x.y"
    # User-Agent as a bot signature; anything browser-shaped gets through.
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        sys.exit(f"error: GET {endpoint} returned HTTP {e.code}")
    except urllib.error.URLError as e:
        sys.exit(f"error: GET {endpoint} failed: {e.reason}")

    # strict=False: some product descriptions contain raw newlines inside the
    # JSON string value (seen on Posture Pal), which json.loads rejects by
    # default even though it's otherwise well-formed.
    data = json.loads(raw, strict=False)
    if isinstance(data, dict) and "error" in data:
        sys.exit(f"error: {data['error']}")
    return data


def trial_label(seconds):
    if not seconds:
        return None
    days = seconds / 86400
    if days <= HOURS_PHRASING_MAX_DAYS and seconds % 3600 == 0:
        return f"Free for {int(seconds / 3600)} hours"
    return f"Free for {round(days)} days"


def normalize(product):
    price = float(product["price"])
    has_trial = bool(product.get("hasTrial"))
    seconds = product.get("trialDuration") or 0
    return {
        "id": product["id"],
        "kpayId": product.get("kpayId"),
        "name": (product.get("name") or "").strip(),
        "price": price,
        "priceStr": f"{price:.2f}",
        "hasTrial": has_trial,
        "trialSeconds": seconds if has_trial else None,
        "trialLabel": trial_label(seconds) if has_trial else None,
    }


def compare(data, path):
    try:
        html = open(path, encoding="utf-8").read()
    except OSError as e:
        sys.exit(f"error: cannot read {path}: {e}")

    def first(pattern):
        m = re.search(pattern, html, re.I)
        return m.group(1).strip() if m else None

    checks = [
        ("price (sidebar)", first(r"<strong>Price:</strong>\s*\$([\d.]+)"), data["priceStr"]),
        ("price (JSON-LD)", first(r'"price":\s*"([\d.]+)"'), data["priceStr"]),
        ("trial (sidebar)", first(r"<strong>Trial:</strong>\s*([^<]+)"), data["trialLabel"]),
    ]

    print(f"\ncompare: {path}\n")
    drift = 0
    for label, page, store in checks:
        same = (page is None and store is None) or (
            page is not None and store is not None and page.lower() == store.lower()
        )
        mark = "ok  " if same else "DIFF"
        if not same:
            drift += 1
        print(f"  {mark} {label:18} page={page!r:30} kiezelpay={store!r}")
    print(f"\n{drift} field(s) need attention\n")
    return drift


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("product_id", nargs="?", type=int, help="KiezelPay productId (not the numeric APP_ID/kpayId)")
    p.add_argument("--list", action="store_true", help="list every product in the account")
    p.add_argument("--compare", metavar="PATH")
    args = p.parse_args()

    key = read_api_key()

    if args.list:
        result = get("productList", key)
        rows = sorted(result.get("products", []), key=lambda x: x["name"].strip().lower())
        for prod in rows:
            print(f"{prod['id']:>8}  kpayId={prod['kpayId']:<12} ${prod['price']:<6} {prod['name'].strip()}")
        return

    if args.product_id is None:
        p.error("productId is required unless --list is given")

    product = get("product", key, productId=args.product_id)
    data = normalize(product)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    if args.compare:
        compare(data, args.compare)


if __name__ == "__main__":
    main()
