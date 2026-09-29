---
name: sync-kiezelpay-pricing
description: Refresh price and trial length across app landing pages from the live KiezelPay account. Use when the user asks to update prices, check for price drift, or sync pricing/trial info for one or all apps.
---

# Sync price and trial length from KiezelPay

**KiezelPay is the source of truth for price and trial length.** The Garmin store API can never answer this - every app it lists is reported free with no trial, because payment happens in-app through KiezelPay, not through Garmin's own purchase flow (see `fetch-garmin-app.py`'s "Never overwrite" note and `.claude/skills/sync-garmin-apps/SKILL.md`). This skill is what actually keeps price/trial correct; `sync-garmin-apps` deliberately leaves those two fields alone.

Prices and trial lengths **do change** - this is a live account setting, not a one-time fact. Re-run this whenever the user asks to check or refresh pricing, not just when building a new page.

## 1. The API

- Base URL: `https://kiezelpay.com/api/merchant`
- Auth: query parameter `key=<API_KEY>` (not a header). The key lives in `.env` at the repo root (`API_KEY=...`), which is gitignored - never print it, commit it, or send it anywhere but `kiezelpay.com`.
- Get/rotate a key at the account's dashboard: `https://kiezelpay.com/account/api` (requires login - ask the user for the key or a fresh one if `.env` is missing or the key stops working).
- **Rate limit: 20 requests/minute per key.** Exceeding it returns `{"error": "Too many requests..."}` with HTTP 200 (not 429) - the script's `get()` treats any `"error"` key in the body as a hard failure, so this surfaces immediately rather than silently returning garbage.
- **Cloudflare blocks the default Python User-Agent** in front of this API (a bare `urllib.request.urlopen()` call gets HTTP 403). [scripts/fetch-kiezelpay-price.py](../../../scripts/fetch-kiezelpay-price.py) already sends a browser-shaped `User-Agent`; don't strip that if you touch the script.
- Two endpoints matter:
  - `GET /productList?key=...` - every product in the account: `id` (KiezelPay's productId), `kpayId` (the numeric `APP_ID` from that app's own `source/kpay/kpay_config.mc` in its Connect IQ project - use this to double check you have the right product if a name is ambiguous), `name`, `price`. No trial info here.
  - `GET /product?key=...&productId=<id>` - full detail for one product, including `hasTrial` (bool) and `trialDuration` (seconds). This is the one that answers "what's the real price and trial length."
- Some product `description` fields contain a raw newline inside the JSON string (seen on Posture Pal) - technically invalid JSON. The script already parses with `strict=False` to tolerate it; don't "fix" this by re-encoding, it'll break on that product.

## 2. Mapping an app to its KiezelPay productId

Every app already on the landing site has a `"kiezelpayProductId"` field in [scripts/apps-registry.json](../../../scripts/apps-registry.json), set once and reused - **don't re-derive it by fuzzy-matching names every run.** KiezelPay's product `name` field is a free-text label the developer typed once and often drifts from the Garmin store's actual listing name (e.g. KiezelPay calls it "20-20-20 Eye Shield: Intelligent Break Reminder", the store and this site call it "20-20-20 Eye Saver: Smart Vision Breaks" - same app, same productId `76351`, different label). Matching by name on every run is exactly the kind of fragile, silently-wrong logic to avoid.

**Adding a brand-new app**: run `scripts/fetch-kiezelpay-price.py --list`, find the product by eyeballing the name (or cross-check the `kpayId` column against the new project's `kpay_config.mc` `APP_ID` if the name is ambiguous), and add `"kiezelpayProductId": <id>` to that app's entry in `apps-registry.json`.

## 3. Refreshing one app

```bash
python3 scripts/fetch-kiezelpay-price.py <productId> --compare apps/<page>.html
```

This prints the live `price` / `priceStr` / `trialLabel`, then a compare table against what's currently on the page (sidebar `.store-meta` Price/Trial lines and the JSON-LD `offers.price`). Any `DIFF` row needs the page fixed to match KiezelPay - **KiezelPay always wins**, this is the opposite of `sync-garmin-apps`'s "store always wins" rule, and deliberately so, since KiezelPay is the only source that actually knows this fact.

Fields to update on drift, all three every time (they must never disagree with each other):
1. JSON-LD `"offers": { "@type": "Offer", "price": "X.XX", "priceCurrency": "USD" }`
2. Sidebar `<p><strong>Price:</strong> $X.XX (one-time)</p>`
3. Sidebar `<p><strong>Trial:</strong> <trialLabel></p>`

Trial phrasing convention already established across every page: 1-3 day trials are written in hours ("Free for 24 hours" / "48 hours" / "72 hours"), 4+ day trials are written in days ("Free for 5 days" / "7 days"). `trial_label()` in the script reproduces this; match it by hand if editing a page directly.

## 4. Refreshing every app ("update all prices")

Loop `apps-registry.json` entries that have both a `page` and a `kiezelpayProductId`, calling `--compare` for each. **Space the calls out** (a couple of seconds apart) - 16+ apps in a tight loop will trip the 20/minute limit; if you see the rate-limit error, pause and resume rather than retrying immediately.

Only touch a page when the compare shows a real `DIFF` - don't rewrite a page that already matches, and don't touch anything else on the page while you're in there (this skill's job is exactly these two facts, nothing else).

## 5. Never invent a number

If `--list` or `--compare` can't find the app (wrong productId, app not in the KiezelPay account yet, or the account API is unreachable), leave the page's existing price/trial alone and say so - don't guess, and don't copy a number from the Garmin store description even if it looks plausible (that's sourced prose, not the live setting, and the two can disagree the moment the developer changes the price in the KiezelPay dashboard without editing the store listing).
