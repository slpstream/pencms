# SortableJS

Vendored copy of [`sortablejs`](https://github.com/SortableJS/Sortable) for the
PenCMS Site Navigation Menu Builder (`admin-settings-navigation.php`). Loaded
synchronously from `/assets/vendor/sortablejs/sortable.min.js`.

## Version

- `sortablejs@1.15.2`

## Source

- https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js

Stored as `sortable.min.js` (with a `Sortable.min.js` symlink) per project vendor
convention; filename has no version suffix so script tags do not churn on every
upgrade — the version is tracked here instead.

## License

- MIT (see upstream `LICENSE` at
  https://github.com/SortableJS/Sortable/blob/master/LICENSE)

## Integrity

- SHA-256 of `sortable.min.js` (vendored file, 44 581 bytes):
  `ca68430703c4f5960e90735867c6e94d29b5a3de37107d8100e5a301007e9e6e`

To verify after re-download:

```sh
sha256sum sortable.min.js
```

Re-vendor with:

```sh
curl -sSL -o sortable.min.js \
  https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js
ln -sf sortable.min.js Sortable.min.js
sha256sum sortable.min.js
```

## Why this exact version

- Pinned to `1.15.2` for reorderable drag-and-drop slots in the Site Navigation Menu
  Builder (`frontend-php/src/admin/js/settings-navigation.js`).

## Upgrade procedure

1. Bump the version in this README.
2. Re-download `sortable.min.js` from the corresponding jsDelivr URL.
3. Update the SHA-256 above.
4. Smoke-test Site Navigation: drag and drop items between/within slots, save and verify slot order.
