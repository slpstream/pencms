# CodeJar

Vendored copy of [`codejar`](https://github.com/antonmedv/codejar) for the
PenCMS Theme Customize editor. Loaded as an ES module from
`/assets/vendor/codejar/codejar.js` on `admin-customize.php` only (bridged
to `window.CodeJar` for classic `customize.js`).

## Version

- `codejar@4.2.0`

## Source

- https://cdn.jsdelivr.net/npm/codejar@4.2.0/dist/codejar.js

Filename has no version suffix so the script tag does not churn on every
upgrade — the version is tracked here instead.

## License

- MIT (see upstream `LICENSE` at
  https://github.com/antonmedv/codejar/blob/master/LICENSE)

## Integrity

- SHA-256 of `codejar.js` (vendored file, 16 894 bytes):
  `82a66955e2c2785967b12a819c7feb80c1a2bb9db9a210e1c60d5816ba6c25c4`

To verify after re-download:

```sh
sha256sum codejar.js
```

Re-vendor with:

```sh
curl -sSL -o codejar.js \
  https://cdn.jsdelivr.net/npm/codejar@4.2.0/dist/codejar.js
sha256sum codejar.js
```

## Upgrade procedure

1. Bump the version in this README.
2. Re-download `codejar.js` from the corresponding jsDelivr URL.
3. Update the SHA-256 above.
4. Smoke-test Theme Customize: open Twig/CSS → edit → dirty → Save; AI
   write-through; Dark/Light toggle.
