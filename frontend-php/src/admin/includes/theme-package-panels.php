<?php
// Theme Settings: Import New + Export panels.
?>
                <!-- ═══════════════════════════════════════════════════════
                     TAB 2: IMPORT NEW
                     ═══════════════════════════════════════════════════════ -->
                <div x-show="activeTab === 'import'" class="space-y-6 max-w-4xl" x-cloak>
                    <p class="text-xs text-forge-dark font-serif leading-relaxed -mt-2">
                        Add a new theme to this PenCMS installation. Imported themes appear alongside built-in themes in the Installed Themes tab.
                    </p>

                    <!-- Themes Directory Banner / Highlight Callout -->
                    <div class="pen-card p-5 bg-card border border-border border-l-4 border-l-rust shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div class="flex items-start gap-3.5 min-w-0">
                            <div class="w-10 h-10 rounded bg-rust/10 border border-rust/20 flex items-center justify-center flex-shrink-0 text-rust mt-0.5">
                                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-.778.099-1.533.284-2.253" />
                                </svg>
                            </div>
                            <div>
                                <h4 class="text-sm font-bold font-sans uppercase tracking-tight text-primary flex items-center gap-2">
                                    <span>PenCMS Theme Collection</span>
                                    <span class="text-[9px] px-1.5 py-0.5 bg-rust text-white font-mono font-bold tracking-wider uppercase">Directory</span>
                                </h4>
                                <p class="text-xs text-forge-dark font-serif leading-relaxed mt-1">
                                    Looking for more themes? Browse dozens of third-party and community themes at
                                    <a href="https://themes.pencms.org/"
                                       target="_blank"
                                       rel="noopener noreferrer"
                                       class="font-bold text-rust hover:underline inline-flex items-center gap-0.5 font-sans">
                                        PenCMS Themes
                                        <svg class="w-3 h-3 inline-block ml-0.5 opacity-80" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/></svg>
                                    </a>
                                    (<a href="https://themes.pencms.org/" target="_blank" rel="noopener noreferrer" class="font-mono text-rust hover:underline text-[11px]">https://themes.pencms.org/</a>).
                                    Download a complete theme zip to upload below, or copy its repository URL to install directly.
                                </p>
                            </div>
                        </div>
                        <a href="https://themes.pencms.org/"
                           target="_blank"
                           rel="noopener noreferrer"
                           class="flex-shrink-0 px-4 py-2.5 bg-rust hover:bg-rust-dark text-white font-sans font-bold text-xs uppercase tracking-wider transition-colors shadow-sm inline-flex items-center justify-center gap-1.5 border border-rust whitespace-nowrap">
                            <span>Visit PenCMS Themes</span>
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/></svg>
                        </a>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <!-- Upload ZIP Card -->
                        <div class="pen-card p-8 bg-card border-border flex flex-col items-center text-center relative">
                            <div class="w-14 h-14 rounded-full bg-rust/10 flex items-center justify-center mb-5">
                                <svg class="w-7 h-7 text-rust" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
                                </svg>
                            </div>
                            <h3 class="text-base font-bold font-sans uppercase tracking-tight text-primary mb-2">Upload Theme</h3>
                            <p class="text-xs text-forge-dark font-serif leading-relaxed mb-6">
                                Upload a PenCMS theme package as a <span class="font-mono">.zip</span> file.
                                The archive should contain a valid <span class="font-mono">theme.json</span> and the theme's template files.
                            </p>
                            <!-- Dropzone -->
                            <div class="w-full">
                                <input type="file"
                                       x-ref="importZip"
                                       accept=".zip,application/zip"
                                       class="hidden"
                                       @change="onImportFileChange($event)">
                                <div x-show="!importFile"
                                     @click="$refs.importZip.click()"
                                     @dragover.prevent="importDragActive = true"
                                     @dragleave.prevent="importDragActive = false"
                                     @drop.prevent="onImportDrop($event)"
                                     class="w-full border-2 border-dashed rounded-lg p-6 bg-canvas/50 transition-colors cursor-pointer"
                                     :class="importDragActive ? 'border-rust bg-rust-wash' : 'border-border hover:border-rust/60'">
                                    <p class="text-xs text-forge-mid font-sans font-bold uppercase tracking-wider">
                                        Drag & drop a .zip file here
                                    </p>
                                    <p class="text-[10px] text-forge-mid/60 mt-1">or click to browse</p>
                                </div>
                                <div x-show="importFile" x-cloak
                                     class="w-full border border-border rounded-lg p-4 bg-canvas text-left">
                                    <div class="flex items-center justify-between gap-3">
                                        <div class="min-w-0">
                                            <p class="text-xs font-bold text-primary truncate" x-text="importFile?.name"></p>
                                            <p class="text-[10px] font-mono text-forge-mid" x-text="importFileSize"></p>
                                        </div>
                                        <button type="button"
                                                class="text-[10px] font-bold uppercase tracking-wider text-danger hover:underline flex-shrink-0"
                                                @click="clearImportFile()"
                                                :disabled="importing">
                                            Remove
                                        </button>
                                    </div>
                                    <button type="button"
                                            class="pen-btn-primary pen-btn-sm w-full mt-4"
                                            :disabled="importing"
                                            @click="importTheme(false)">
                                        <span x-text="importing ? 'Installing…' : 'Install Theme'"></span>
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- URL / Git Card -->
                        <div class="pen-card p-8 bg-card border-border flex flex-col items-center text-center relative">
                            <div class="w-14 h-14 rounded-full bg-rust/10 flex items-center justify-center mb-5 text-rust">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-7 h-7"><rect width="256" height="256" fill="none"/><line x1="32" y1="128" x2="224" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M168,128c0,64-40,96-40,96s-40-32-40-96,40-96,40-96S168,64,168,128Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                            </div>
                            <h3 class="text-base font-bold font-sans uppercase tracking-tight text-primary mb-2">Install from URL</h3>
                            <p class="text-xs text-forge-dark font-serif leading-relaxed mb-6">
                                Install from <span class="font-mono">themes.pencms.org</span>, a public GitHub or GitLab HTTPS repository, or point to a direct
                                <span class="font-mono">.zip</span> download URL.
                            </p>
                            <div class="w-full space-y-3">
                                <input type="url"
                                       x-model="importUrl"
                                       placeholder="https://themes.pencms.org/packages/editorial.zip"
                                       class="pen-input w-full bg-canvas text-xs"
                                       :class="importUrlError ? 'border-danger' : ''"
                                       :disabled="importingUrl"
                                       :aria-invalid="importUrlError ? 'true' : 'false'"
                                       @input="onImportUrlInput()"
                                       @blur="validateImportUrlField()"
                                       @keydown.enter.prevent="installFromUrl(false)">
                                <p x-show="importUrlError"
                                   x-cloak
                                   class="text-[10px] text-danger text-left font-sans leading-relaxed"
                                   x-text="importUrlError"></p>
                                <button type="button"
                                        class="pen-btn-primary pen-btn-sm w-full"
                                        :disabled="importingUrl || !importUrl.trim()"
                                        @click="installFromUrl(false)">
                                    <span x-text="importingUrl ? 'Fetching…' : 'Fetch & Install'"></span>
                                </button>
                            </div>
                        </div>
                    </div>
                  <br>
                </div>


                <!-- ═══════════════════════════════════════════════════════
                     TAB: EXPORT
                     ═══════════════════════════════════════════════════════ -->
                <div x-show="activeTab === 'export'" class="space-y-6 max-w-4xl" x-cloak>
                    <p class="text-xs text-forge-dark font-serif leading-relaxed -mt-2">
                        Package the current site look as a shareable theme base for
                        <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span>.
                        Includes templates/CSS, baked Style Settings, vendored registry fonts,
                        and a fresh <span class="font-mono">screenshot.webp</span> when preview capture is available.
                        Use <span class="font-mono">Import New</span> on another install to upload the zip.
                    </p>

                    <div class="pen-card p-8 bg-card border-border space-y-6">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1.5">Theme slug</label>
                                <input type="text"
                                       x-model="packageSlug"
                                       @blur="packageSlug = sanitizePackageSlug(packageSlug)"
                                       placeholder="my-theme"
                                       class="pen-input w-full font-mono text-xs"
                                       :disabled="packaging || packageInstalling">
                                <p class="text-[10px] text-forge-mid font-serif mt-1.5">Lowercase letters, numbers, and hyphens. Cannot be <span class="font-mono">custom</span>.</p>
                            </div>
                            <div>
                                <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1.5">Display name</label>
                                <input type="text"
                                       x-model="packageName"
                                       placeholder="My Theme"
                                       class="pen-input w-full text-xs"
                                       :disabled="packaging || packageInstalling">
                            </div>
                            <div class="md:col-span-2">
                                <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1.5">Author</label>
                                <input type="text"
                                       x-model="packageAuthor"
                                       placeholder="Your name or organization"
                                       class="pen-input w-full text-xs"
                                       :disabled="packaging || packageInstalling">
                            </div>
                        </div>

                        <div class="flex flex-col sm:flex-row gap-3 pt-2 border-t border-border/30">
                            <button type="button"
                                    class="pen-btn-secondary pen-btn-sm flex items-center justify-center gap-2"
                                    :disabled="packaging || packageInstalling"
                                    @click="downloadPackageZip()">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><g transform="rotate(180 12 12)"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></g></svg>
                                <span x-text="packaging ? 'Packaging…' : 'Download .zip'"></span>
                            </button>
                            <button type="button"
                                    class="pen-btn-primary pen-btn-sm"
                                    :disabled="packaging || packageInstalling"
                                    @click="savePackageAsInstalled(false)">
                                <span x-text="packageInstalling ? 'Saving…' : 'Save as installed theme'"></span>
                            </button>
                        </div>
                    </div>
                  <br>
                </div>
