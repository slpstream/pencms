<?php
// Theme Settings: overwrite confirmation modals.
?>
    <!-- Overwrite Theme Confirmation Modal -->
    <div x-show="confirmOverwriteModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal-danger min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="confirmOverwriteModalOpen = false" @keydown.escape.window="confirmOverwriteModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Overwrite Theme</h3>
                <button @click="confirmOverwriteModalOpen = false" class="text-forge-mid hover:text-forge-black">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    A theme named <strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border" x-text="pendingImportSlug"></strong> already exists.
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose">
                    Overwriting will replace the existing theme directory with the uploaded archive. This cannot be undone. Site-private custom themes based on this theme will not be affected.
                </p>
            </div>
            <div class="pen-modal-footer">
                <button @click="confirmOverwriteModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
                <button @click="confirmOverwriteImport()" class="pen-btn pen-btn-danger pen-btn-sm">Overwrite Theme</button>
            </div>
        </div>
    </div>

    <!-- Overwrite Packaged Theme Confirmation Modal -->
    <div x-show="confirmPackageOverwriteModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal-danger min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="confirmPackageOverwriteModalOpen = false" @keydown.escape.window="confirmPackageOverwriteModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Overwrite Theme</h3>
                <button @click="confirmPackageOverwriteModalOpen = false" class="text-forge-mid hover:text-forge-black">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    A theme named <strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border" x-text="pendingPackageSlug"></strong> already exists.
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose">
                    Overwriting will replace the existing install theme directory with the packaged version. This cannot be undone.
                </p>
            </div>
            <div class="pen-modal-footer">
                <button @click="confirmPackageOverwriteModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
                <button @click="confirmOverwritePackageInstall()" class="pen-btn pen-btn-danger pen-btn-sm">Overwrite Theme</button>
            </div>
        </div>
    </div>
