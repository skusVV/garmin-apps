#!/usr/bin/env python3
"""Fetch a Connect IQ store listing and emit it as normalised JSON.

The Connect IQ store is the source of truth for every app page in this repo.
This script does the deterministic half of a sync: fetch, parse, normalise.
Rewriting the prose into page sections is left to the caller.

Usage:
    scripts/fetch-garmin-app.py <store-url-or-uuid> [options]

Options:
    --locale LOCALE   store listing locale to read (default: en)
    --devices         include the full compatible-device name list
    --raw             also include the unparsed description / whatsNew text
    --compare PATH    diff the store values against an existing app page

Notes:
    services.garmin.com rejects unauthenticated calls; the apps.garmin.com
    proxy does not, so everything goes through the proxy.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape

API = "https://apps.garmin.com/api/appsLibraryExternalServices/api/asw"
SCREENSHOT_BASE = "https://services.garmin.com/appsLibraryExternalServices/api/screenshots"
ICON_BASE = "https://services.garmin.com/appsLibraryExternalServices/api/icons"
STORE_URL = "https://apps.garmin.com/apps/{}"

# Only 2 and 3 are confirmed against this repo's own apps; the rest are the
# conventional Connect IQ ordering. typeId is always emitted so a bad guess
# is visible rather than silent.
APP_TYPES = {"1": "Watch Face", "2": "Watch App", "3": "Widget", "4": "Data Field", "5": "Music App"}

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
DATE_RE = re.compile(r"^\s*([A-Z][a-z]{2,8}\.?\s+\d{1,2},\s*\d{4})\s*:?\s*$")
BULLET_RE = re.compile(r"^\s*[-*•·]\s+")


def get(path):
    req = urllib.request.Request(f"{API}/{path}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"error: GET {path} returned HTTP {e.code}")
    except urllib.error.URLError as e:
        sys.exit(f"error: GET {path} failed: {e.reason}")


def clean(text):
    """Normalise store text to the typography this site uses.

    The store copy is full of em dashes and curly quotes; the site uses plain
    hyphens and straight quotes throughout.
    """
    if not text:
        return ""
    for bad, good in (
        ("—", "-"), ("–", "-"), ("‘", "'"), ("’", "'"),
        ("“", '"'), ("”", '"'), (" ", " "), ("﻿", ""),
    ):
        text = text.replace(bad, good)
    text = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_description(text):
    """Split store copy into intro paragraphs and heading/bullet sections.

    Store descriptions are written as intro prose, then repeated blocks of
    "Some heading:" followed by "- bullet" lines. That maps one-to-one onto the
    page's .app-desc paragraphs and .features (h3 + ul) blocks.
    """
    intro, sections, current = [], [], None
    para = []

    def flush():
        """Emit the buffered prose lines as one unwrapped paragraph."""
        if not para:
            return
        text = " ".join(para)
        para.clear()
        if current is None:
            intro.append(text)
        else:
            current.setdefault("paragraphs", []).append(text)

    # Store copy is hard-wrapped, so a paragraph break is a blank line, never
    # a newline. Anything else would split mid-sentence.
    for block in re.split(r"\n\s*\n", text):
        for line in block.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if BULLET_RE.match(stripped):
                flush()
                if current is None:
                    current = {"heading": None, "bullets": []}
                    sections.append(current)
                current["bullets"].append(BULLET_RE.sub("", stripped))
            elif stripped.endswith(":") and len(stripped) < 90:
                flush()
                current = {"heading": stripped[:-1].strip(), "bullets": []}
                sections.append(current)
            elif current is not None and current["bullets"] and not para:
                # Wrapped continuation of the last bullet.
                current["bullets"][-1] += " " + stripped
            else:
                para.append(stripped)
        flush()
    flush()
    return intro, sections


def parse_changelog(text):
    """Parse the whatsNew field into dated entries, newest first.

    Entries are date-headed blocks. Store order is inconsistent (Tai Chi lists
    oldest first), so always sort rather than trusting the given order.
    """
    entries, current = [], None
    for line in text.split("\n"):
        stripped = line.strip()
        m = DATE_RE.match(line)
        if m:
            current = {"date": m.group(1).replace(".", ""), "items": []}
            entries.append(current)
            continue
        if not stripped or current is None:
            continue
        if BULLET_RE.match(stripped):
            current["items"].append(BULLET_RE.sub("", stripped))
        elif current["items"]:
            current["items"][-1] += " " + stripped
        else:
            current["items"].append(stripped)

    for e in entries:
        try:
            d = datetime.strptime(e["date"], "%B %d, %Y")
        except ValueError:
            d = datetime.min
        e["iso"] = d.strftime("%Y-%m-%d") if d != datetime.min else None
    entries.sort(key=lambda e: e["iso"] or "0000-00-00", reverse=True)
    return entries


def ms_to_iso(ms):
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def build(app_id, locale, want_devices, want_raw):
    app = get(f"apps/{app_id}")

    locs = {l["locale"]: l for l in app.get("appLocalizations", [])}
    loc = locs.get(locale) or locs.get("en") or (list(locs.values()) or [{}])[0]
    if locale not in locs:
        print(f"warning: locale '{locale}' not published; using '{loc.get('locale')}'", file=sys.stderr)

    description = clean(loc.get("description", ""))
    whats_new = clean(loc.get("whatsNew", ""))
    intro, sections = parse_description(description)

    rating = None
    if app.get("reviewCount"):
        rating = {"value": app.get("averageRating"), "count": app.get("reviewCount")}

    out = {
        "id": app["id"],
        "storeUrl": STORE_URL.format(app["id"]),
        # Store names are kept verbatim apart from stray whitespace - some
        # listings have a leading space, and the em dashes in names like
        # "Fasting Tracker - IF, Ketosis & Autophagy" are part of the product
        # name, so they are not normalised the way body copy is.
        "name": (loc.get("name") or "").strip(),
        "version": app.get("latestExternalVersion"),
        "typeId": app.get("typeId"),
        "type": APP_TYPES.get(str(app.get("typeId")), f"typeId {app.get('typeId')}"),
        "categoryId": app.get("categoryId"),
        "status": app.get("status"),
        "rating": rating,
        "downloadCount": app.get("downloadCount"),
        "deviceCount": len(app.get("compatibleDeviceTypeIds", [])),
        "screenshots": [f"{SCREENSHOT_BASE}/{s}" for s in app.get("screenshotFileIds", [])],
        "iconUrl": f"{ICON_BASE}/{app['iconFileId']}" if app.get("iconFileId") else None,
        "permissions": app.get("permissions", []),
        "releaseDate": ms_to_iso(app.get("releaseDate")),
        "firstApprovalDate": ms_to_iso(app.get("firstApprovalDate")),
        "descriptionIntro": intro,
        "descriptionSections": sections,
        "changelog": parse_changelog(whats_new),
        # Locales the STORE LISTING is translated into. This is not the set of
        # languages the app's own UI supports - that lives in the app's source,
        # not in this payload. Never write it into an "App languages" section.
        "storeListingLocales": sorted(locs),
        # The store reports every app here as free with no trial because
        # payment runs through KiezelPay in-app. Price and trial length are
        # NOT available from this API.
        "hasTrialMode": app.get("hasTrialMode"),
        "paymentModel": app.get("paymentModel"),
    }

    if want_devices:
        names = {d["id"]: d["name"] for d in get("deviceTypes")}
        out["devices"] = sorted(
            names.get(str(i), f"unknown ({i})") for i in app.get("compatibleDeviceTypeIds", [])
        )
    if want_raw:
        out["rawDescription"] = description
        out["rawWhatsNew"] = whats_new
    return out


def compare(data, path):
    """Report deterministic drift between the store and an existing page."""
    try:
        html = open(path, encoding="utf-8").read()
    except OSError as e:
        sys.exit(f"error: cannot read {path}: {e}")

    def first(pattern):
        m = re.search(pattern, html, re.I)
        return unescape(m.group(1).strip()) if m else None

    rating = data["rating"]
    checks = [
        ("version (sidebar)", first(r"<strong>Version:</strong>\s*([^<]+)"), data["version"]),
        ("version (JSON-LD)", first(r'"softwareVersion":\s*"([^"]+)"'), data["version"]),
        ("rating (JSON-LD)", first(r'"ratingValue":\s*"?([\d.]+)"?'),
         str(rating["value"]) if rating else None),
        ("reviews (JSON-LD)", first(r'"reviewCount":\s*"?(\d+)"?'),
         str(rating["count"]) if rating else None),
        ("devices (sidebar)", first(r"<strong>Devices:</strong>\s*([^<]+)"),
         f"{data['deviceCount']} supported"),
        ("app name", first(r"<h1>([^<]+)</h1>"), data["name"]),
    ]

    page_shots = re.findall(rf"{re.escape(SCREENSHOT_BASE)}/([0-9a-f-]+)", html)
    store_shots = [u.rsplit("/", 1)[1] for u in data["screenshots"]]
    checks.append(("screenshots", ",".join(dict.fromkeys(page_shots)) or None, ",".join(store_shots)))

    latest = data["changelog"][0]["date"] if data["changelog"] else None
    on_page = bool(latest) and latest.lower() in unescape(html).lower()
    checks.append(("newest changelog entry", ("present" if on_page else "missing") if latest else None, latest))

    print(f"\ncompare: {path}\n")
    drift = 0
    for label, page, store in checks:
        if page is None and store is None:
            # The store has nothing to say and the page makes no claim, e.g. an
            # unrated app with no aggregateRating block. Not drift.
            same = True
        else:
            same = page is not None and store is not None and page.lower() == store.lower()
        if label == "newest changelog entry" and latest:
            same = on_page
        elif label == "devices (sidebar)" and page:
            # Pages round down deliberately ("100+ supported"); only flag a
            # claim the store cannot back up.
            n = re.search(r"\d+", page)
            same = bool(n) and int(n.group(0)) <= data["deviceCount"]
        mark = "ok  " if same else "DIFF"
        if not same:
            drift += 1
        print(f"  {mark} {label:24} page={page!r:44} store={store!r}")
    print(f"\n{drift} field(s) need attention\n")
    return drift


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("app", help="store URL or app UUID")
    p.add_argument("--locale", default="en")
    p.add_argument("--devices", action="store_true")
    p.add_argument("--raw", action="store_true")
    p.add_argument("--compare", metavar="PATH")
    args = p.parse_args()

    m = UUID_RE.search(args.app)
    if not m:
        sys.exit(f"error: no app UUID found in {args.app!r}")

    data = build(m.group(0).lower(), args.locale, args.devices, args.raw)
    if data["status"] != "APPROVED":
        print(f"warning: store status is {data['status']}, not APPROVED", file=sys.stderr)

    print(json.dumps(data, indent=2, ensure_ascii=False))
    if args.compare:
        compare(data, args.compare)


if __name__ == "__main__":
    main()
