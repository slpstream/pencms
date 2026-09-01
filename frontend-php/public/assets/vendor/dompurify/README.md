# DOMPurify

Vendored copy of [`DOMPurify`](https://github.com/cure53/DOMPurify) for the
PenCMS admin AI sidebar. Loaded synchronously from
`/assets/vendor/dompurify/purify.min.js`.

## Version

- `dompurify@3.4.14`

## Source

- https://cdn.jsdelivr.net/npm/dompurify@3.4.14/dist/purify.min.js
  Stored as `purify.min.js` per project vendor convention; filename has no
  version suffix so the script tag in `_admin-head.php` doesn't churn on
  every upgrade — the version is tracked here instead.

## License

- Dual-licensed: Apache-2.0 OR MPL-2.0 (see upstream
  https://github.com/cure53/DOMPurify/blob/main/LICENSE)

## Integrity

- SHA-256 of `purify.min.js` (vendored file, 29 204 bytes):
  `c2f26ea4fc0d88141c9aa430eb515ac86fce59418ceebd85fa475b87a8d6c3e6`

To verify after re-download:

```sh
sha256sum purify.min.js
```

Re-vendor with:

```sh
curl -sSL -o purify.min.js \
  https://cdn.jsdelivr.net/npm/dompurify@3.4.14/dist/purify.min.js
sha256sum purify.min.js
```

## Why this exact version

- Pinned to a specific patch (`3.4.14`) to avoid silent breakage from
  upstream changes.
- Used by `frontend-php/src/admin/js/ai-markdown-sanitize.js` via
  `window.DOMPurify` after `marked` postprocess, so AI chat HTML assigned
  through Alpine `x-html` is sanitized with a browser-grade allowlist
  instead of regex tag filters.

## Upgrade procedure

1. Bump the version in this README.
2. Re-download `purify.min.js` from the corresponding jsDelivr URL.
3. Update the SHA-256 and byte size above.
4. Smoke-test AI sidebar markdown: fenced code copy button (SVG), images,
   links, and that raw `<script>` / `javascript:` hrefs do not execute.
