<?php
/**
 * _admin-icon-sprite.php
 *
 * SVG <symbol> definitions for the icons that appear exactly once
 * (structurally) throughout admin-editor.php. Rendered hidden; each
 * icon is drawn via <svg><use href="#icon-name"></use></svg> at its
 * call site.
 *
 * Icons repeated 2+ times live in admin_icon() (_admin-icons.php)
 * instead, since those are simple enough to be a PHP helper function
 * rather than a sprite sheet.
 *
 * Add new one-off icons here rather than inlining raw <svg> markup
 * directly into admin-editor.php.
 */
?>
    <svg style="display:none" aria-hidden="true">
        <symbol id="icon-ai-command" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </symbol>
        <symbol id="icon-alert-triangle" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </symbol>
        <symbol id="icon-apply-arrow" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <g transform="translate(256, 0) scale(-1, 1)">
            <path d="M30.93,198.72C47.39,181.19,90.6,144,152,144v48l80-80L152,32V80C99.2,80,31.51,130.45,24,195.54A4,4,0,0,0,30.93,198.72Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            </g>
        </symbol>
        <symbol id="icon-attach-paperclip" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none"/>
            <line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
            <line x1="128" y1="40" x2="128" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
        </symbol>
        <symbol id="icon-checkmark-thin" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <polyline points="40 144 96 200 224 72" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
        </symbol>
        <symbol id="icon-chevron-down" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5">
            </path>
        </symbol>
        <symbol id="icon-chevron-up" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5">
            </path>
        </symbol>
        <symbol id="icon-clear-conversation" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <line x1="216" y1="60" x2="40" y2="60" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            <line x1="88" y1="20" x2="168" y2="20" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            <path d="M200,60V208a8,8,0,0,1-8,8H64a8,8,0,0,1-8-8V60" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
        </symbol>
        <symbol id="icon-copy-clipboard" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <polyline points="168 168 216 168 216 40 88 40 88 88" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            <rect x="40" y="88" width="128" height="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
        </symbol>
        <symbol id="icon-download" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none"/>
            <polyline points="88 208 88 152 60 192 32 152 32 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <path d="M128,152v56h16a28,28,0,0,0,0-56Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <polyline points="148 32 148 92 208 92" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <path d="M208,224V88L152,32H56a8,8,0,0,0-8,8v68" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
        </symbol>
        <symbol id="icon-drag-handle" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z">
            </path>
        </symbol>
        <symbol id="icon-expand-arrows" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
        </symbol>
        <symbol id="icon-external-link" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14">
            </path>
        </symbol>
        <symbol id="icon-eye-outline" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <path d="M128,56C48,56,16,128,16,128s32,72,112,72,112-72,112-72S208,56,128,56Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
        </symbol>
        <symbol id="icon-image-replace" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12">
            </path>
        </symbol>
        <symbol id="icon-lock-closed" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </symbol>
        <symbol id="icon-magic-wand" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none"/>
            <line x1="216" y1="128" x2="216" y2="176" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="192" y1="152" x2="240" y2="152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="80" y1="40" x2="80" y2="88" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="56" y1="64" x2="104" y2="64" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="168" y1="184" x2="168" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="152" y1="200" x2="184" y2="200" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="144" y1="80" x2="176" y2="112" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <rect x="21.49" y="105.37" width="213.02" height="45.25" rx="8" transform="translate(-53.02 128) rotate(-45)" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
        </symbol>
        <symbol id="icon-palette" viewBox="0 0 256 256">
            <path d="M200.77,53.89A103.27,103.27,0,0,0,128,24h-1.07A104,104,0,0,0,24,128c0,43,26.58,79.06,69.36,94.17A32,32,0,0,0,136,192a16,16,0,0,1,16-16h46.21a31.81,31.81,0,0,0,31.2-24.88,104.43,104.43,0,0,0,2.59-24A103.28,103.28,0,0,0,200.77,53.89ZM84,168a12,12,0,1,1,12-12A12,12,0,0,1,84,168Zm0-56a12,12,0,1,1,12-12A12,12,0,0,1,84,112Zm44-24a12,12,0,1,1,12-12A12,12,0,0,1,128,88Zm44,24a12,12,0,1,1,12-12A12,12,0,0,1,172,112Z">
            </path>
        </symbol>
        <symbol id="icon-panel-toggle-left" viewBox="0 0 256 256">
            <g transform="scale(-1,1) translate(-256,0)">
            <rect width="256" height="256" fill="none" />
            <rect x="48" y="48" width="160" height="160" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="48" x2="128" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="80" x2="208" y2="80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="112" x2="208" y2="112" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="144" x2="208" y2="144" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="176" x2="208" y2="176" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            </g>
        </symbol>
        <symbol id="icon-panel-toggle-preview" viewBox="0 0 256 256">
            <g transform="rotate(90 128 128) scale(-1,1) translate(-256,0)">
            <rect width="256" height="256" fill="none" />
            <rect x="48" y="48" width="160" height="160" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="48" x2="128" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="80" x2="208" y2="80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="112" x2="208" y2="112" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="144" x2="208" y2="144" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="176" x2="208" y2="176" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            </g>
        </symbol>
        <symbol id="icon-panel-toggle-right" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <rect x="48" y="48" width="160" height="160" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="48" x2="128" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="80" x2="208" y2="80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="112" x2="208" y2="112" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="144" x2="208" y2="144" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="128" y1="176" x2="208" y2="176" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
        </symbol>
        <symbol id="icon-plus-thin" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4">
            </path>
        </symbol>
        <symbol id="icon-refresh-sync" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </symbol>
        <symbol id="icon-save-disk" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none"/>
            <path d="M224,120v88a16,16,0,0,1-16,16H48a16,16,0,0,1-16-16V48A16,16,0,0,1,48,32h88z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            <polyline points="136 32 136 88 224 88" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
        </symbol>
        <symbol id="icon-send-plane" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <line x1="108" y1="148" x2="160" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            <path d="M223.69,42.18a8,8,0,0,0-9.87-9.87l-192,58.22a8,8,0,0,0-1.25,14.93L108,148l42.54,87.42a8,8,0,0,0,14.93-1.25Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
        </symbol>
        <symbol id="icon-settings-gear" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.757.426 1.757 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.757-2.924 1.757-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.757-.426-1.757-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z">
            </path>
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z">
            </path>
        </symbol>
        <symbol id="icon-sparkle-ai" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <path d="M84.27,171.73l-55.09-20.3a7.92,7.92,0,0,1,0-14.86l55.09-20.3,20.3-55.09a7.92,7.92,0,0,1,14.86,0l20.3,55.09,55.09,20.3a7.92,7.92,0,0,1,0,14.86l-55.09,20.3-20.3,55.09a7.92,7.92,0,0,1-14.86,0Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            <line x1="176" y1="16" x2="176" y2="64" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            <line x1="224" y1="72" x2="224" y2="104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            <line x1="152" y1="40" x2="200" y2="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            <line x1="208" y1="88" x2="240" y2="88" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
        </symbol>
        <symbol id="icon-spinner" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4">
            </circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z">
            </path>
        </symbol>
        <symbol id="icon-stop-square" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="1" />
        </symbol>
        <symbol id="icon-tabs-grid" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none"/>
            <circle cx="176" cy="88" r="16" fill="currentColor"/>
            <rect x="72" y="48" width="152" height="120" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <path d="M192,168v32a8,8,0,0,1-8,8H40a8,8,0,0,1-8-8V88a8,8,0,0,1,8-8H72" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <path d="M72,156.69l46.34-46.35a8,8,0,0,1,11.32,0L187.31,168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
        </symbol>
        <symbol id="icon-toast-error" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z">
            </path>
        </symbol>
        <symbol id="icon-toast-success" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7">
            </path>
        </symbol>
        <symbol id="icon-toggle-markdown" viewBox="8 48 240 160">
            <rect width="256" height="256" fill="none" />
            <rect x="16" y="56" width="224" height="144" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <polyline points="56 152 56 104 88 136 120 104 120 152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <line x1="176" y1="104" x2="176" y2="152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
            <polyline points="200 128 176 152 152 128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
        </symbol>
        <symbol id="icon-trash" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16">
            </path>
        </symbol>
        <symbol id="icon-undo-arrow" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <polyline points="24 56 24 104 72 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
            <path d="M67.59,192A88,88,0,1,0,65.77,65.77L24,104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
        </symbol>
        <symbol id="icon-upload" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none"/>
            <polyline points="148 32 148 92 208 92" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <path d="M48,108V40a8,8,0,0,1,8-8h96l56,56v20" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="108" y1="152" x2="148" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="148" y1="152" x2="108" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="80" y1="152" x2="40" y2="152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="60" y1="152" x2="60" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="216" y1="152" x2="176" y2="152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
            <line x1="196" y1="152" x2="196" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
        </symbol>
        <symbol id="icon-wrench-tools" viewBox="0 0 256 256">
            <rect width="256" height="256" fill="none" />
            <path d="M73,217A24,24,0,0,1,39,183l63.77-58.28A64,64,0,0,1,184,36.65L144,80l5.66,26.34L176,112l43.35-40a64,64,0,0,1-88.1,81.2Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
        </symbol></svg>
