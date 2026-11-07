# Branding and Logo usage

This document records the approved implementation guidance for the BabelBeam wordmark and related brand assets. Use these rules when adding the visual identity to the app, documentation, marketing, or CI packaging.

Files added to the repo
- public/brand/logo-full.svg — monogram + beam + two-tone wordmark
- public/brand/logo-light.svg — variant for dark backgrounds (wordmark in white/ice)
- public/brand/logo-monogram.svg — monogram only with transparent background
- public/brand/logo-beam.svg — beam only for layered compositions
- public/brand/icon.svg — square app icon composition (monogram + beam)
- design/tokens.css — design tokens including beam gradient and color variables
- apps/web/src/components/Logo/Logo.tsx — React Logo component that respects variants and theme

Usage rules (summary)
- Provide both light and dark variants; do not rely on CSS inversion (filter: invert) to fix contrast.
- Preserve vector transparency; do not ship a logo with a white rectangular background.
- Use the monogram-only icon for very small chrome (favicons, small buttons).
- Keep at least 12–16 px clear space around the entire wordmark in UI layouts.
- When displaying on dark backgrounds use `logo-light.svg` to ensure legibility; on light backgrounds use `logo-full.svg`.
- The beam is provided as a separate asset so it can be animated or adjusted without re-exporting the whole wordmark.

SVG export checklist for designers
- Include named groups/ids: `#monogram`, `#beam`, `#wordmark-babel`, `#wordmark-beam`.
- Avoid embedding raster filters that some browsers ignore.
- Provide flattened gradients and preserve alpha/transparency.
- Export PNG/WebP at 512x512 (maskable), 192x192, and Apple 180x180 for the manifest.

Accessibility
- If the logo conveys brand-only decorative meaning, use `aria-hidden="true"` and include a separate visible site title for screen readers.
- If the logo conveys navigation or site identity, provide an accessible name (`alt` or inline `<title>`/`<desc>`) and avoid duplicative visible text.

Implementation notes for engineers
- Prefer using the `Logo` React component in shared header/footer UI.
- For themeable swaps, either use inline SVG or the dedicated `logo-light.svg`/`logo-full.svg` files.
- Cache static assets via the app's asset pipeline; prefer immutable filename hashing in production.

Production rasters
- `apps/web/public/brand/logo-full.png` is the navy wordmark for light surfaces.
- `apps/web/public/brand/logo-light.png` is the ice wordmark for dark surfaces. It is a recolor of the approved art, not a CSS invert.
- `apps/web/public/brand/icon.png` and `apps/web/public/icons/` are cropped from `assets/reference/approved-logo-showcase.png` with the white showcase field removed.
- Regenerate them with `python scripts/export_brand_assets.py`.
- The SVG files under `public/brand/` are geometric placeholders. Do not use them in the header.

The parish brochure PDFs in `docs/references/` set the dark layout, small-caps labels, and Speak / Interpret / Follow story. They are not proof of a finished feature.
