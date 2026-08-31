<?php
// Theme Settings: Import / Export tab buttons.
?>
                    <button @click="setTab('import')"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'import' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Import New
                    </button>
                    <button @click="setTab('export')"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'export' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'"
                            x-show="$store.app.hasCap('write:theme')" x-cloak>
                        Export
                    </button>
