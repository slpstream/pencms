# marked

Vendored copy of [`marked`](https://github.com/markedjs/marked) for the
PenCMS admin AI sidebar. Loaded synchronously from
`/assets/vendor/marked/marked.min.js`.

## Version

- `marked@18.0.5`

## Source

- https://cdn.jsdelivr.net/npm/marked@18.0.5/lib/marked.umd.min.js
  (the UMD browser bundle; this is what jsDelivr serves when a plain
  `marked.min.js` URL is requested — the package ships no top-level
  `marked.min.js`). Stored as `marked.min.js` per project vendor
  convention; filename has no version suffix so the script tag in
  `_admin-head.php` doesn't churn on every upgrade — the version is
  tracked here instead.

## License

- BSD-3-Clause (see upstream `LICENSE` at
  https://github.com/markedjs/marked/blob/master/LICENSE)

## Integrity

- SHA-256 of `marked.min.js` (vendored file, 42 858 bytes):
  `8855491f5f19e2584a87785cb1982ae831547c38d324989f9ea77cb3f7fd4217`

To verify after re-download:

```sh
sha256sum marked.min.js
```

Re-vendor with:

```sh
curl -sSL -o marked.min.js \
  https://cdn.jsdelivr.net/npm/marked@18.0.5/lib/marked.umd.min.js
sha256sum marked.min.js
```

## Why this exact version

- Pinned to a specific minor (`18.0.5`) to avoid silent breakage from
  upstream changes.
- Used at module-init time in `frontend-php/src/admin/js/ai-sidebar.js`
  via `new marked.Marked()`, with the renderer overrides described in
  `pencms/core/marked-implementation-plan.md`. The renderer signatures
  (`{ tokens }`, `{ text, lang }`, `{ tokens, depth }`) and
  `hooks.preprocess` / `hooks.postprocess` are stable in the v15+ line.

## Upgrade procedure

1. Bump the version in this README.
2. Re-download `marked.min.js` from the corresponding jsDelivr URL.
3. Update the SHA-256 above.
4. Smoke-test against the verification checklist in
   `pencms/core/marked-implementation-plan.md` (Step 6).