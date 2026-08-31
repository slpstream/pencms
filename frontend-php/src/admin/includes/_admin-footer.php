<?php
/**
 * PenCMS Admin Footer Layout
 */
?>
    <footer class="relative border-t-[5px] border-rust bg-rust-wash py-2 text-center text-[10px] text-steel-muted uppercase tracking-[0.14em] font-serif font-bold select-none">
        <div class="max-w-7xl mx-auto px-4">
            <p>PenCMS<span x-show="$store.app.edition === 'pro'" x-cloak> Pro</span> &bull; Headless, API-first Markdown Flat-File CMS with built-in MCP server &bull; Open Source<span x-show="$store.app.edition === 'pro'" x-cloak> Core</span>, MIT License &bull; <span id="cache-status-container" class="cursor-pointer hover:text-rust transition-colors duration-150 normal-case" title="Click to synchronize SQLite cache with disk changes">Cache: <span id="cache-status-text" class="underline">Loading...</span></span></p>
        </div>
        <!-- Corner Resize Decors -->
        <svg class="absolute bottom-0 right-0 w-3 h-3 text-steel-muted/30 pointer-events-none" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
            <line x1="12" y1="0" x2="0" y2="12" />
            <line x1="12" y1="4" x2="4" y2="12" />
            <line x1="12" y1="8" x2="8" y2="12" />
        </svg>
    </footer>

    <!-- Core Client Scripts -->
    <script src="js/api.js"></script>
    <script src="js/store.js"></script>
    <?php if (isset($pageScript) && !empty($pageScript)): ?>
        <script src="js/<?= htmlspecialchars($pageScript) ?>"></script>
    <?php endif; ?>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const container = document.getElementById('cache-status-container');
            const statusText = document.getElementById('cache-status-text');
            
            let lastSync = 0;
            let clientOffset = 0;

            function formatTimeAgo() {
                if (!lastSync) return 'never';
                const currentServerTime = (Date.now() / 1000) - clientOffset;
                const seconds = Math.floor(currentServerTime - lastSync);
                if (seconds < 5) return 'just now';
                if (seconds < 60) return `${seconds}s ago`;
                const minutes = Math.floor(seconds / 60);
                if (minutes < 60) return `${minutes}m ago`;
                const hours = Math.floor(minutes / 60);
                if (hours < 24) return `${hours}h ago`;
                return new Date(lastSync * 1000).toLocaleDateString();
            }

            async function updateStatus(fetchNewData = true) {
                try {
                    if (fetchNewData) {
                        const status = await window.api.request('/cache/status');
                        lastSync = status.last_sync;
                        clientOffset = (Date.now() / 1000) - status.server_now;
                        statusText.dataset.entryCount = status.entry_count;
                    }
                    const entryCount = statusText.dataset.entryCount || 0;
                    const timeStr = formatTimeAgo();
                    statusText.textContent = `${entryCount} entries (Synced ${timeStr})`;
                } catch (err) {
                    console.error('Failed to fetch cache status:', err);
                    statusText.textContent = 'Error';
                }
            }

            if (container && statusText) {
                // Wait briefly for Auth/Vault client initialization
                setTimeout(() => updateStatus(true), 500);

                // Auto-refresh the relative timestamp every 60s (does not query network)
                setInterval(() => updateStatus(false), 60000);

                container.addEventListener('click', async () => {
                    const originalText = statusText.textContent;
                    if (originalText.includes('Syncing...')) return;
                    statusText.textContent = 'Syncing...';
                    container.classList.add('animate-pulse');
                    try {
                        await window.api.request('/cache/sync', { method: 'POST' });
                        await updateStatus(true);
                    } catch (err) {
                        console.error('Manual cache sync failed:', err);
                        statusText.textContent = 'Sync Failed';
                        setTimeout(() => updateStatus(true), 3000);
                    } finally {
                        container.classList.remove('animate-pulse');
                    }
                });
            }
        });
    </script>
</body>
</html>
