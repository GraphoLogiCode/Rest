# Rest frontend

A responsive React + TypeScript app built with Vite. The botanical green/gold wordmark is a lightweight interpretation of the supplied brand reference; the original image is preserved in `public/rest-brand-reference.png` and displayed in Settings.

## Run locally

```sh
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (normally http://127.0.0.1:5173). `npm run build` checks TypeScript and creates `dist/`. `npm run preview` serves the production build locally.

## Test on a phone

Run `npm run dev:phone` from `frontend`, connect the phone and Mac to the same Wi-Fi, then open Vite's printed **Network** URL on port 5174 on the phone. Keep the Mac awake and the server running. This command makes the preview available to other devices on that network. Stop it with Ctrl+C when finished. The normal `npm run dev` command stays local to the Mac on port 5173.

The `phone` mode forces local account storage and disables AI previews and the local model proxy. Use it for layout, navigation, local check-ins, and product browsing. The catalog uses the loopback backend on port 8000 through `/rest-api`; start the backend for live catalog results. Account sign-in, cross-device sync, and installable-app testing belong in a separate HTTPS test, before GPU deployment if desired.

If the network blocks connections between devices (common on campus and guest Wi-Fi), connect both devices to a private Wi-Fi network or phone hotspot. No cable or app installation is needed. Each browser/device has its own local notes and routines; there is no cross-device sync. The AI service is still not connected.

Routine IDs use `crypto.getRandomValues`, which works over local-network HTTP as well as HTTPS. Camera/photo-library selection uses the browser's file picker; the app does not request a live camera stream.

## Heading font

Main headings and well-being category titles use **MADE Gentle** by MadeType, with Georgia as a fallback. The supplied reference wordmark and body font remain separate. The personal-use font was downloaded from [the designer's DaFont listing](https://www.dafont.com/made-gentle.font) for this local prototype. Its license notice is preserved in `public/fonts/MADE-Gentle-LICENSE.txt`.

The local `public/fonts/made-gentle-personal-use.otf` is excluded from Git. On another checkout, provide the font at that path for personal testing or replace the `@font-face` source with an appropriately licensed webfont. Obtain the appropriate commercial license before distributing a commercial app; the current local build copies the personal-use font into `dist`.

## Implemented

- Dashboard with sleep, mental well-being, and social connection cards; no invented user history.
- Daily check-in with sleep duration, mood, connection, optional notes, and recent history. Saving again updates today's entry.
- Morning/evening routine steps, completion by local calendar date, and removal.
- Session-only before/after photo uploads, dates, side-by-side comparison, and an adjustable reveal slider. Supports JPEG, PNG, and WebP up to 10 MB; validates image decoding.
- Separate optional AI illustration screen. Disabled honestly until an API is configured.
- Local JSON export and confirmed deletion of this browser's saved data.
- Three-loop loading screen with genuine lazy-loading fallback, retry on app load failure, optional determinate progress, and reduced-motion support. Settings has a manual preview; no artificial startup delay.
- Responsive sidebar/mobile navigation, keyboard focus styles, labeled controls, and live status messages.

Check-ins and routines use `localStorage` under `rest.local.v1`, **without encryption or account sync**. Photos use object URLs in memory and disappear on refresh; they are never stored in localStorage. This is a local frontend preview, not production photo storage or an authenticated application. External Google Fonts is optional; system fonts work if unavailable.

## SDXL / IP-Adapter integration

See [the proposed API contract](src/services/README.md). Inference code stays in `../ml/scenario-visualization/`; this frontend does not change or invoke its CLI directly.

Copy `.env.example` to `.env.local` and set `VITE_ILLUSTRATION_API_URL` **only after a matching API exists**. Restart Vite after changing environment configuration. No secret belongs in a `VITE_` variable: those values are public in the browser bundle.

## Source guide

- `src/App.tsx`: application shell, dashboard, check-in, routine, privacy controls.
- `src/components/Journal.tsx`: local photo comparison and consent-based generation UI.
- `src/components/Brand.tsx`: botanical illustration, wordmark, and three-loop mark.
- `src/components/LoadingScreen.tsx`: reusable loading/error screen.
- `src/services/storage.ts`: local persistence and data shapes.
- `src/services/illustration.ts`: configurable job API adapter and response validation.
- `src/styles.css`: responsive visual system and reduced-motion behavior.

### Authenticated cloud previews

Set `VITE_REST_API_URL`, `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`
together to enable Supabase email/password sign-in in the face-preview feature.
Without those settings, local preview behavior is preserved. Cloud jobs use the
signed-in JWT, private image downloads and temporary browser blob URLs. The product
note stays in the browser and is not sent to the model. See
[`deploy/aws/README.md`](../deploy/aws/README.md) for server configuration and limits.
`npm test` checks the illustration adapter's cloud and local request contracts.

## Saved account data and product suggestions

When cloud mode is configured, the app-wide sign-in panel loads check-ins and
routines from the authenticated API. Users explicitly enable service storage.
Local browser entries are not uploaded automatically: the import control copies
only missing check-in dates and routine IDs, keeps account entries on conflicts,
and leaves local originals intact. Partial imports can be retried. Account data
is never written to the old local-storage key. Account changes clear displayed
check-ins, routines and journal photos; responses from an old account are ignored.

Configure `VITE_REST_API_URL`, `VITE_SUPABASE_URL`, and
`VITE_SUPABASE_PUBLISHABLE_KEY`, plus backend CORS and the routine database
migration. Existing accounts can sign in; account creation/password recovery
remain outside this change. Development without cloud configuration retains the
local notes/routine mode. The product browser uses `/rest-api` through Vite to a
local backend on port 8000, or the configured API URL in cloud mode.

**Products & suggestions** provides category/search, reviewed label details,
profile preferences, explained rule matches and adding a product to the morning
routine. No candidate records are shown before verification. Real recommendations
may be empty; the app does not invent products or relax hard constraints.

Verification used synthetic accounts on a disposable loopback backend: check-in
and routine saves survived browser reload, sign-out cleared account content,
and a second account did not see the first account's data. This does not replace
verification against deployed Supabase/Postgres and AWS.

The explicit local import was also exercised with synthetic check-ins and routine steps. An unanswered sleep value stayed null and displayed “Sleep not logged”; local source entries were retained.

## Product beside an AI preview

Skin journal → AI preview offers an optional selector from the reviewed product
catalog. The completed illustration shows a reference card with the selected
brand, name, category, available price and product link. The selection is captured
when the job starts; it does not condition the model or represent product effects.
The card stacks below the images on narrow phone screens. Official product photos appear in the selector and result card, using HTTPS image
URLs attributed in the catalog. If an image is unavailable, the details and product
link remain usable. Images are displayed with their original proportions.

For a same-Wi-Fi phone test with the Mac model, start the backend on port 8000,
start the model with the exact phone-facing origin configured (see
[LOCAL_SETUP.md](../ml/scenario-visualization/LOCAL_SETUP.md#phone-preview-with-the-mac-model)),
then run `npm run dev:phone-model`. Open the network URL Vite prints on the phone.
This mode uses local browser data and the Mac model, without enabling cloud account
storage. The ordinary `dev:phone` command continues to offer a UI-only preview.

## Install Rest on a phone

Rest now includes a web app manifest, PNG home-screen icons, standalone launch,
and Settings & privacy → Keep Rest on your phone. Supporting browsers expose the
Install Rest button when their installation prompt becomes available. iPhone
users can use Safari's Share → Add to Home Screen flow; Android users can use
Chrome's Install app menu. Phone installation requires the deployed HTTPS URL.
A plain HTTP same-Wi-Fi development URL is only a preview.

Production builds generate `/sw.js` with an explicit list of public app-shell
assets. The worker never handles account APIs, private photo downloads, uploads,
authorized requests, query-string callbacks or foreign origins. It does not queue
account writes offline. The offline notice asks users to reconnect for cloud
saving, product matching and uploads. Updates wait until the user chooses Update
Rest or the older app windows close; choosing Update clears temporary tab photos.

Run `npm test` and `npm run build`. The PWA tests cover private-route bypass,
offline shell fallback, PNG dimensions and user-triggered install prompts. A real
iPhone/Android install and sign-in test must still be performed at the hosted URL.
The deployment must rebuild with these files: `frontend/build/`, the manifest,
icons, install component and registration entrypoint are included by the source
packager and managed Docker build. Opening the installed app calls the hosted API
and does not require the Mac to remain on.

This release installs from the web; it does not produce a signed App Store IPA or
Play Store APK. Store distribution is a separate packaging and signing workflow.
