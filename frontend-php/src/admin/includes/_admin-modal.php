<?php
/**
 * _admin-modal.php
 *
 * Renders one of the small "confirm this action" dialogs used throughout
 * admin-editor.php (Resume Draft, Delete Asset, Add Fragment, Remove Fragment).
 *
 * These all share the same pen-modal-overlay / pen-modal-header / body / footer
 * skeleton; only the Alpine show-flag, title, body markup, and footer buttons
 * differ per instance. This does NOT try to templatize the one-off Shortcode
 * Editor modal, which has a materially different structure (form fields,
 * dynamic template content) and is left as its own inline block.
 *
 * Usage:
 *   admin_modal([
 *       'show_var' => 'deleteAssetModalOpen',       // Alpine var controlling x-show
 *       'title'    => 'Delete Asset',
 *       'danger'   => true,                          // use pen-modal-danger styling
 *       'body'     => '...raw HTML for pen-modal-body...',
 *       'footer'   => '...raw HTML for pen-modal-footer buttons...',
 *   ]);
 *
 * $body and $footer are raw HTML (not escaped) since they contain Alpine
 * bindings (x-text, @click) that must pass through untouched — same trust
 * level as the rest of this template file.
 */

function admin_modal(array $config): void
{
    $showVar = $config['show_var'];
    $title = $config['title'];
    $danger = $config['danger'] ?? false;
    $body = $config['body'];
    $footer = $config['footer'];
    $bodySpacing = $config['body_spacing'] ?? 'space-y-3';

    $modalClass = $danger ? 'pen-modal-danger' : 'pen-modal';
    ?>
    <div x-show="<?= htmlspecialchars($showVar) ?>" x-cloak class="pen-modal-overlay p-4" style="display:none"
        x-transition>
        <div class="<?= $modalClass ?> min-w-0 w-full max-w-[480px] sm:min-w-[480px]"
            @click.away="<?= htmlspecialchars($showVar) ?> = false"
            @keydown.escape.window="<?= htmlspecialchars($showVar) ?> = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title"><?= htmlspecialchars($title) ?></h3>
                <button @click="<?= htmlspecialchars($showVar) ?> = false" class="text-forge-mid hover:text-forge-black">
                    <?php admin_icon('close', 'w-5 h-5'); ?>
                </button>
            </div>
            <div class="pen-modal-body <?= htmlspecialchars($bodySpacing) ?>">
                <?= $body ?>
            </div>
            <div class="pen-modal-footer">
                <?= $footer ?>
            </div>
        </div>
    </div>
    <?php
}
