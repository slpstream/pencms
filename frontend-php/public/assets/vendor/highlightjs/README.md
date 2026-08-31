# highlight.js (subset)

Vendored **ES module** subset of [`highlight.js`](https://highlightjs.org/)
for CodeJar syntax highlighting on Theme Customize. Loaded only from
`admin-customize.php` (bridged to `window.hljs`).

Token colors are defined in `frontend-php/src/admin/css/admin-customize.css`
(no upstream theme CSS shipped).

## Version

- `highlight.js@11.11.1` (cdn-release)

## Files

| Path | Purpose |
|------|---------|
| `es/core.min.js` | Core highlighter |
| `es/languages/css.min.js` | CSS |
| `es/languages/twig.min.js` | Twig (depends on `xml`) |
| `es/languages/xml.min.js` | XML/HTML (Twig subLanguage) |

## Source

```
https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/es/core.min.js
https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/es/languages/css.min.js
https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/es/languages/twig.min.js
https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/es/languages/xml.min.js
```

## License

- BSD-3-Clause (see https://github.com/highlightjs/highlight.js/blob/main/LICENSE)

## Integrity

| File | Bytes | SHA-256 |
|------|------:|---------|
| `es/core.min.js` | 20 445 | `bfcca5550cb9d62482162e1d1fb90c822d2d35036b556544817441b795b7103c` |
| `es/languages/css.min.js` | 13 284 | `8024c97edb80335f7aded04543de058770eab34939b9b2db8334fb8aa16f0e45` |
| `es/languages/twig.min.js` | 2 519 | `b117c6cdb3ef6e03058ac2eafbdc020f181b485f4a71830bc553856d1c955a6b` |
| `es/languages/xml.min.js` | 2 021 | `2d843265c0bdd3e50f107e6473196b5f525c0ea68de83c40f9f30ffbbea6896f` |

Re-vendor (from this directory):

```sh
curl -sSL -o es/core.min.js \
  https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/es/core.min.js
curl -sSL -o es/languages/css.min.js \
  https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/es/languages/css.min.js
curl -sSL -o es/languages/twig.min.js \
  https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/es/languages/twig.min.js
curl -sSL -o es/languages/xml.min.js \
  https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/es/languages/xml.min.js
sha256sum es/core.min.js es/languages/*.min.js
```

## Upgrade procedure

1. Bump the version in this README.
2. Re-download the four files from the matching cdn-release tag.
3. Update SHA-256 values above.
4. Smoke-test Customize Twig + CSS highlighting in dark and light skins.
