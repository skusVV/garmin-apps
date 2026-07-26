---
name: sync-garmin-apps
description: Sync a landing page with its Connect IQ store listing. Use when the user asks to update, refresh, or re-sync an app page, or to add a landing page for a store app - given a store URL, an app name, or "update all apps". Pulls title, description, changelog, screenshots, version, rating, and device count from the store and rewrites the page.
---

# Sync a landing page from the Connect IQ store

**The store listing is the source of truth.** Where the page and the store disagree about anything the store knows, the store wins. The exceptions are listed under "Never overwrite" below - get those wrong and you delete information the store does not have.

Images are never downloaded. Screenshots are hotlinked from `services.garmin.com` by URL.

## 1. Resolve the app

[scripts/apps-registry.json](../../../scripts/apps-registry.json) maps every store app to its page. Look the app up there by `id` or `name`:

- `page` is set -> **update** that page (section 3).
- `page` is `null` -> **create** a new page (section 4), then add the registry `page` value.
- Not in the registry at all -> add an entry, then create the page. Get `name` and `type` from the fetch output, never by guessing.

If the user gave a store URL, the UUID in it is the `id`. If they gave a name, match it case-insensitively against `name`. If nothing matches, ask rather than guessing which page they mean.

## 2. Fetch the store data

```bash
python3 scripts/fetch-garmin-app.py <store-url-or-uuid> --compare apps/<page>.html
```

Drop `--compare` when creating a new page. Add `--devices` when you need the compatible-device names, and `--raw` to see the unedited store text.

The `--compare` table is a checklist, not a diff to apply blindly. Every `DIFF` row must end up either fixed or consciously rejected, and say which in your summary.

Useful fields in the JSON:

| Field | Feeds |
| --- | --- |
| `name` | `<title>`, `<h1>`, JSON-LD `name`, the card in [index.html](../../../index.html) |
| `descriptionIntro` | the `.app-desc` paragraphs |
| `descriptionSections` | one `.features` block per section (`heading` -> `<h3>`, `bullets` -> `<li>`) |
| `changelog` | the "Latest updates" `.features` block, newest first |
| `screenshots` | the `.screenshots` strip and JSON-LD `screenshot` |
| `version`, `rating`, `deviceCount` | `.store-meta` sidebar **and** JSON-LD, which must agree |
| `type` | the `.app-type` badge on both the page and the index card |
| `storeUrl` | all 5 store links on the page |

## 3. Update an existing page

Work through these in order. Every one is a real place the data lives - missing one leaves the page self-contradictory.

1. **Head** - `<title>` and `<meta name="description">` if the store name or pitch changed; `og:title`, `og:description`, `og:image` (first screenshot).
2. **JSON-LD** - `name`, `softwareVersion`, `description`, `screenshot`, `aggregateRating` (`ratingValue` / `reviewCount`), `downloadUrl` / `sameAs` / `url`. Omit `aggregateRating` entirely when `rating` is `null`; never emit a zero rating.
3. **`<h1>` and `.app-type` badge.**
4. **Screenshots strip** - one `<img>` per URL in `screenshots`, in store order. Write a descriptive `alt` per shot based on what the surrounding copy says that screen does. If the page has no `.screenshots` div and the store has screenshots, add one after `.app-header`.
5. **`.app-desc` paragraphs** - from `descriptionIntro`.
6. **`.features` blocks** - from `descriptionSections`. Re-use an existing block when its heading still matches; add, drop, and reorder to match the store.
7. **"Latest updates"** - from `changelog`, newest first, formatted `<li><strong>July 23, 2026</strong> - what changed</li>`. Merge a multi-item entry into one readable sentence group rather than nesting lists. Cap at the 5 most recent.
8. **Sidebar `.store-meta`** - Version, Rating (`3.8 out of 5 (5 reviews)`), Devices.
9. **FAQ** - only add or amend an entry when the store change makes an existing answer wrong or leaves an obvious new question unanswered. Do not regenerate the FAQ wholesale.
10. **[index.html](../../../index.html)** - the `.app-card` title, `.app-type`, and blurb, plus the matching `ItemList` entry name. The blurb is a 1-2 sentence squeeze of the intro, not a copy of it.
11. **[sitemap.xml](../../../sitemap.xml)** - bump `<lastmod>` to today for the changed page.

Re-run the `--compare` command at the end. It should report 0 fields needing attention, except for a deliberately rounded device count.

## 4. Create a new page

Copy the closest existing page as the skeleton - [apps/tai-chi.html](../../../apps/tai-chi.html) for an activity app, [apps/fasting.html](../../../apps/fasting.html) for a widget - then run every step in section 3 against it. Also:

- Pick the filename as a short kebab-case slug of the app name (`muay-thai.html`), and use it consistently in the canonical URL, `og:url`, JSON-LD `url`, sitemap entry, and index card link.
- Pick an emoji for `.app-icon` / `.app-icon-lg` and two `.badge` labels that match the app's niche.
- Add the standard closing sections: "Compatible Garmin watches", "How to install X on your Garmin watch", "Frequently asked questions".
- Add a new `<url>` block to [sitemap.xml](../../../sitemap.xml) with `<priority>0.8</priority>`.
- Add a new `.app-card` to [index.html](../../../index.html) and a new `ItemList` entry, and bump the app count in the index `<title>`, meta description, hero copy, and `WebSite` JSON-LD description.
- Set the registry entry's `page`.
- Health-adjacent apps need a `.disclaimer-box`.

## Never overwrite

The store payload does **not** contain these. Carry them over from the existing page, or ask the user when creating a new one:

- **Price and trial length.** Payment runs through KiezelPay, so the API reports every app as free with `hasTrialMode: false`. That is an artefact, not the truth. Never write "free" onto a paid app.
- **App UI languages.** `storeListingLocales` is which locales the *store listing* is translated into (28 for Tai Chi) - not which languages the *app* speaks (6). They are unrelated. Never feed `storeListingLocales` into an "App languages" section.
- **Category** in the sidebar. The API returns a bare `categoryId` with no public name lookup.
- **Hand-written FAQ answers** that the store change does not contradict.

## House style

- Store copy uses em dashes and curly quotes; the site does not. `fetch-garmin-app.py` already converts them in description and changelog text - keep it that way in anything you write by hand. App *names* keep their punctuation verbatim.
- Escape `&` as `&amp;` in HTML and keep it bare in JSON-LD.
- Keep the terse, benefit-first voice. Feature bullets are fragments, not sentences.
- Do not invent features, device names, or dates that are absent from the store payload.

## Reporting back

State per app: fields changed, fields left alone and why, and anything the store could not answer (price, trial, category). If `--compare` still shows a `DIFF` you chose not to act on, say so explicitly.
