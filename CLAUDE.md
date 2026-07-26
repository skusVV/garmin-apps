# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static, hand-written HTML marketing site for 13 Garmin Connect IQ apps by Vitalii Skus. No build step, no framework, no package manager, no tests. Files are served verbatim by GitHub Pages.

- Repo: `github.com/skusVV/garmin-apps`
- Live base URL: `https://skusvv.github.io/garmin-apps/` (a GitHub Pages **project** site, so every page lives under the `/garmin-apps/` path prefix)
- `.nojekyll` at the root disables Jekyll processing

## Running it locally

Open `index.html` in a browser, or serve the directory:

```bash
python3 -m http.server 8000    # then http://localhost:8000/
```

Deploy = commit and push to `main`. GitHub Pages publishes from the repo root.

## Structure

- [index.html](index.html) - the app grid. Every app appears twice here: as an `.app-card` link and as a `ListItem` in the `ItemList` JSON-LD block.
- [apps/](apps/) - one detail page per app, all following the same template (see below)
- [assets/style.css](assets/style.css) - the single stylesheet for the whole site. Dark theme driven by CSS custom properties on `:root` (`--bg`, `--surface`, `--border`, `--text`, `--muted`, `--accent`). No other CSS exists anywhere.
- [sitemap.xml](sitemap.xml), [robots.txt](robots.txt) - hand-maintained
- [scripts/fetch-garmin-app.py](scripts/fetch-garmin-app.py) - fetches a store listing as normalised JSON and, with `--compare <page>`, reports which page fields have drifted from the store. Stdlib only, no dependencies.
- [.claude/skills/sync-garmin-apps/SKILL.md](.claude/skills/sync-garmin-apps/SKILL.md) - the `sync-garmin-apps` skill that drives the fetch-and-rewrite process
- [todo.txt](todo.txt) - a running list of SEO work blocked on missing assets or external actions (Search Console submission, GitHub repo metadata, missing prices). Read it before doing SEO work; update it when an item is unblocked.

## The app detail page template

Every file in [apps/](apps/) is a self-contained copy of the same structure. To add a new app, copy the closest existing page (a rich one like [apps/tai-chi.html](apps/tai-chi.html) or [apps/fasting.html](apps/fasting.html)) and replace content. The shape is:

1. `<head>`: title, meta description, `robots`, **absolute** canonical, `og:type`/`og:url`/`og:title`/`og:description`, optional `og:image`
2. A `SoftwareApplication` JSON-LD block: `name`, `applicationCategory`, `operatingSystem: "Garmin Connect IQ"`, `softwareVersion`, `description`, `url`, `downloadUrl`, `sameAs`, `offers` with price, optionally `screenshot`, `inLanguage`, `aggregateRating`
3. `<header>` with the `GarminApps` logo linking to `../index.html` and a nav link to the Connect IQ store listing
4. `.back` link, `.app-header` (emoji in `.app-icon-lg` + h1 + `.app-type`/`.badge` meta row)
5. Optional `.screenshots` strip
6. `.app-body` two-column grid: content column of `.features` sections (`<h3>` + `<ul>`, or `<ol>` for the numbered install steps) plus a `.faq` block, and an `<aside>` with the `.sidebar-card` CTA and `.store-meta` key/value list
7. Footer linking back to `../index.html`

Conventions worth preserving:

- **Every page ends with a "Compatible Garmin watches" section, a "How to install X on your Garmin watch" numbered list, and a "Frequently asked questions" block.** These are deliberate SEO surfaces, not filler.
- The Garmin store app UUID appears in ~5 places per page (nav link, JSON-LD `downloadUrl`, JSON-LD `sameAs`, install-step link, `.cta-btn`). Change all of them together.
- Screenshots are hotlinked from `https://services.garmin.com/appsLibraryExternalServices/api/screenshots/<uuid>`. `assets/` holds no images; local screenshots are a pending [todo.txt](todo.txt) item.
- Price, version, rating, and device count are duplicated between the JSON-LD `offers`/`softwareVersion`/`aggregateRating` and the `.store-meta` sidebar. Keep them in sync.
- Health-adjacent apps (headache, symptom tracker, pollen, UV, cold plunge, AI coach, fasting) carry a `.disclaimer-box` ("not medical advice"). Add one to any new health app.

## Things that break silently

- **Path depth differs by directory.** Root pages use `assets/style.css` and `apps/foo.html`; detail pages use `../assets/style.css` and `../index.html`. Copying a snippet across levels breaks the link with no error.
- **Canonical, `og:url`, and all JSON-LD `url` values must be absolute and include the `/garmin-apps/` prefix.** A root-relative `/apps/foo.html` resolves to the wrong host path on GitHub Pages.
- **Adding an app page requires three edits, not one**: the page itself, the `.app-card` + `ItemList` entry in [index.html](index.html), and a `<url>` entry in [sitemap.xml](sitemap.xml). `apps/tai-chi.html` is currently missing from the sitemap - add it when next touching that file.
- Only [apps/fasting.html](apps/fasting.html) has a `FAQPage` JSON-LD block in addition to its visible FAQ. Other pages render FAQs without the structured data. Adding it is an improvement, not a regression, but keep the visible copy and the JSON-LD identical if you do.

## Style

Prose across the site uses hyphens, never em dashes. Match the existing terse, benefit-first voice; feature bullets are sentence fragments, not sentences.


## Managed apps

The published Connect IQ apps this site represents. [scripts/apps-registry.json](scripts/apps-registry.json) is the machine-readable source of truth for app IDs and URL slugs; the table below is human reference. Add an app with the `sync-garmin-apps` skill, not by hand-editing either one.

| App | Store URL |
| --- | --- |
| Fasting Tracker - IF, Ketosis & Autophagy | <https://apps.garmin.com/apps/34e32f1b-d25f-40ac-9f0f-d473a76c9f9f> |
| Cold Plunge Pro: Ice Bath & Shiver Protocol | <https://apps.garmin.com/apps/982eb991-005b-4cc8-bda0-aa7807e55094> |
| 20-20-20 Eye Saver: Smart Vision Breaks | <https://apps.garmin.com/apps/a806696c-30eb-4008-a00e-f33eaccb4ca6> |
| Pollen Pulse - 5-Day Allergy Forecast | <https://apps.garmin.com/apps/30652965-1f30-4642-913e-7a29ba74689c> |
| Tai Chi Tracker | <https://apps.garmin.com/apps/cbe6b0ab-b45a-454a-a023-e7973e002901> |
| Outdoor Readiness - Training Conditions Score | <https://apps.garmin.com/apps/a5637e94-cd1f-42c8-a8e0-6dd707b585ca> |
| UV Guard: Sun & Burn Forecast | <https://apps.garmin.com/apps/53361df7-5c70-4b1d-8e36-21c1128e95be> |
| AI Coach | <https://apps.garmin.com/apps/a083e371-7c25-48da-80a1-9d076cc1bf07> |
| BJJ (Brazilian Jiu-Jitsu) | <https://apps.garmin.com/apps/3fc6ffb6-988b-472e-9644-bbb8f9568868> |
| Muay Thai | <https://apps.garmin.com/apps/b855effc-4c62-43c2-a555-06fe7cc96309> |
| Kickboxing Tracker | <https://apps.garmin.com/apps/ea4d6069-5e30-4376-9dfa-287b2e6866da> |
| Blood Pressure Journal | <https://apps.garmin.com/apps/b157783c-8e0f-40d7-8b81-96640cc7e868> |
| Barre Workout Tracker | <https://apps.garmin.com/apps/3a2f8a80-f322-4f9b-af2f-ca070f94e380> |
| Qigong | <https://apps.garmin.com/apps/7919285f-c517-46b8-9b4e-b60bd25ff47d> |
| Reading | <https://apps.garmin.com/apps/1b9caed2-ad53-46bf-b24b-3ca276ffca7f> |
| Posture Pal: Smart Reminders | <https://apps.garmin.com/apps/58a6318f-8669-4561-8017-53217972d18d> |
| Headache Log | <https://apps.garmin.com/apps/92f9721c-a906-4517-a0cd-cba4412036b2> |
| Symptom Tracker | <https://apps.garmin.com/apps/8de4ab53-66c8-431b-9914-27658771a1d3> |
| Dead Hang Pro \| Hands-Free Grip Timer | <https://apps.garmin.com/apps/4f498f82-167f-41a7-8623-ad3add1e43d6> |
