<?php
/**
 * _admin-icons.php
 *
 * Renders the small set of SVG icons that repeat across admin-editor.php
 * (close buttons, eye/eye-slash toggles, link icon, checkmark, plus).
 *
 * Usage:
 *   <?php admin_icon('close'); ?>
 *   <?php admin_icon('close', 'w-5 h-5'); ?>
 *   <?php admin_icon('eye', 'w-4 h-4 text-rust'); ?>
 *
 * The $class param overrides the icon's default size/color classes, so call
 * sites can still control sizing the same way they could with raw inline SVG.
 */

function admin_icon(string $name, ?string $class = null): void
{
    $icons = [
        // Eye (view / visible) — filled, used at w-4 h-4 text-rust
        'eye' => [
            'default_class' => 'w-4 h-4 text-rust',
            'markup' => '<svg xmlns="http://www.w3.org/2000/svg" class="%CLASS%" fill="currentColor" viewBox="0 0 256 256">
    <path d="M247.31,124.76c-.35-.79-8.82-19.58-27.65-38.41C194.57,61.26,162.88,48,128,48S61.43,61.26,36.34,86.35C17.51,105.18,9,124,8.69,124.76a8,8,0,0,0,0,6.5c.35.79,8.82,19.57,27.65,38.4C61.43,194.74,93.12,208,128,208s66.57-13.26,91.66-38.34c18.83-18.83,27.3-37.61,27.65-38.4A8,8,0,0,0,247.31,124.76ZM128,192c-30.78,0-57.67-11.19-79.93-33.25A133.47,133.47,0,0,1,25,128,133.33,133.33,0,0,1,48.07,97.25C70.33,75.19,97.22,64,128,64s57.67,11.19,79.93,33.25A133.46,133.46,0,0,1,231.05,128C223.84,141.46,192.43,192,128,192Zm0-112a48,48,0,1,0,48,48A48.05,48.05,0,0,0,128,80Zm0,80a32,32,0,1,1,32-32A32,32,0,0,1,128,160Z">
    </path>
</svg>',
        ],

        // Eye-slash (hide / hidden) — outline, used at w-4 h-4 text-forge-mid/50
        'eye-slash' => [
            'default_class' => 'w-4 h-4 text-forge-mid/50',
            'markup' => '<svg xmlns="http://www.w3.org/2000/svg" class="%CLASS%" viewBox="0 0 256 256">
    <rect width="256" height="256" fill="none" />
    <line x1="48" y1="40" x2="208" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
    <path d="M154.91,157.6a40,40,0,0,1-53.82-59.2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
    <path d="M135.53,88.71a40,40,0,0,1,32.3,35.53" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
    <path d="M208.61,169.1C230.41,149.58,240,128,240,128S208,56,128,56a126,126,0,0,0-20.68,1.68" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
    <path d="M74,68.6C33.23,89.24,16,128,16,128s32,72,112,72a118.05,118.05,0,0,0,54-12.6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
</svg>',
        ],

        // Link / chain — filled, used at w-3.5 h-3.5
        'link' => [
            'default_class' => 'w-3.5 h-3.5',
            'markup' => '<svg xmlns="http://www.w3.org/2000/svg" class="%CLASS%" fill="currentColor" viewBox="0 0 256 256">
    <path d="M40,88H73a32,32,0,0,0,62,0h81a8,8,0,0,0,0-16H135a32,32,0,0,0-62,0H40a8,8,0,0,0,0,16Zm64-24A16,16,0,1,1,88,80,16,16,0,0,1,104,64ZM216,168H199a32,32,0,0,0-62,0H40a8,8,0,0,0,0,16h97a32,32,0,0,0,62,0h17a8,8,0,0,0,0-16Zm-48,24a16,16,0,1,1,16-16A16,16,0,0,1,168,192Z">
    </path>
</svg>',
        ],

        // Small checkmark — outline, used at w-2.5 h-2.5
        'check' => [
            'default_class' => 'w-2.5 h-2.5',
            'markup' => '<svg class="%CLASS%" fill="none" stroke="currentColor" stroke-width="3.5" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"></path>
</svg>',
        ],

        // Close (X) — outline. Two sizes were used inline (w-3.5 h-3.5 and w-5 h-5);
        // pass $class to pick the size, defaults to the smaller of the two.
        'close' => [
            'default_class' => 'w-3.5 h-3.5',
            'markup' => '<svg class="%CLASS%" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"></path>
</svg>',
        ],

        // Plus — outline, used at w-3.5 h-3.5
        'plus' => [
            'default_class' => 'w-3.5 h-3.5',
            'markup' => '<svg class="%CLASS%" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
</svg>',
        ],

        // Sign Out / Exit — outline
        'sign-out' => [
            'default_class' => 'w-3.5 h-3.5',
            'markup' => '<svg xmlns="http://www.w3.org/2000/svg" class="%CLASS%" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><polyline points="112 40 48 40 48 216 112 216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="112" y1="128" x2="224" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><polyline points="184 88 224 128 184 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>',
        ],
    ];

    if (!isset($icons[$name])) {
        // Fail loudly in dev rather than silently rendering nothing.
        echo "<!-- admin_icon: unknown icon '" . htmlspecialchars($name) . "' -->";
        return;
    }

    $icon = $icons[$name];
    $resolvedClass = $class ?? $icon['default_class'];
    echo str_replace('%CLASS%', htmlspecialchars($resolvedClass), $icon['markup']);
}
