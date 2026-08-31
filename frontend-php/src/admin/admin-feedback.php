<?php
$pageTitle = "PenCMS Feedback";
$currentSection = "feedback";
$pageScript = "feedback.js";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="feedbackInbox" x-init="init()">

    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <?php include "includes/_admin-sidebar.php"; ?>

        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">
            <div class="flex flex-col md:flex-row md:justify-between md:items-end mb-8 gap-4">
                <div>
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                        Feedback
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Inbox of <code class="font-mono text-xs">fb-*</code> stubs for this site.
                        <span class="text-forge-mid font-sans text-xs ml-1">Site: <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span></span>
                    </p>
                </div>
                <button type="button"
                        @click="pullFromRelay()"
                        x-show="$store.app.hasCap('write:posts')"
                        x-cloak
                        :disabled="pulling"
                        class="pen-btn pen-btn-primary flex items-center gap-2 self-start md:self-auto">
                    <svg class="w-4 h-4" :class="pulling ? 'animate-spin' : ''" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                    </svg>
                    <span x-text="pulling ? 'Pulling…' : 'Pull from relay'"></span>
                </button>
            </div>

            <div x-show="pullBanner" x-cloak class="pen-card px-5 py-3 mb-6 flex items-center gap-3">
                <span class="text-[10px] font-bold uppercase tracking-widest"
                      :class="pullBanner && pullBanner.type === 'ok' ? 'text-rust' : 'text-forge-mid'">Result:</span>
                <span class="text-sm font-mono font-bold" x-text="pullBanner && pullBanner.message"></span>
            </div>

            <div class="flex flex-wrap items-center gap-4 mb-8">
                <div class="pen-card px-5 py-3 flex items-center gap-3">
                    <span class="text-[10px] font-bold text-forge-mid uppercase tracking-widest">Unread stubs:</span>
                    <span class="text-sm font-mono font-bold text-rust" x-text="unreadStubCount">0</span>
                </div>
            </div>

            <div class="flex flex-col sm:flex-row justify-between items-stretch sm:items-end border-b border-border mb-8 gap-4">
                <div class="flex gap-1 overflow-x-auto scrollbar-none">
                    <template x-for="status in ['ALL', 'STUB', 'DRAFT']" :key="status">
                        <button type="button" @click="filterStatus = status"
                                class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150 whitespace-nowrap focus:outline-none"
                                :class="filterStatus === status ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                            <span x-text="status === 'ALL' ? 'ALL' : status"></span>
                        </button>
                    </template>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto pb-2 self-start sm:self-auto justify-end">
                    <label class="text-xs font-bold uppercase text-forge-mid whitespace-nowrap" for="feedback-kind-filter">Kind</label>
                    <select id="feedback-kind-filter" x-model="filterKind" class="pen-input text-xs py-1.5 min-w-[140px]">
                        <option value="all">All</option>
                        <option value="contact">Contact</option>
                        <option value="comment">Comment</option>
                    </select>
                </div>
            </div>

            <div class="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(280px,400px)] gap-8 items-start">
                <div>
                    <div class="pen-card bg-card overflow-x-auto" x-show="!loading && filteredItems.length">
                        <table class="w-full text-left">
                            <thead class="bg-canvas border-b border-border">
                                <tr class="text-[9px] uppercase tracking-wider text-forge-mid">
                                    <th class="px-4 py-3">Date</th>
                                    <th class="px-4 py-3">Submitter</th>
                                    <th class="px-4 py-3">Excerpt</th>
                                    <th class="px-4 py-3">Kind</th>
                                    <th class="px-4 py-3">Parent</th>
                                    <th class="px-4 py-3">Status</th>
                                    <th class="px-4 py-3">Source</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-border">
                                <template x-for="item in filteredItems" :key="item.id">
                                    <tr @click="select(item)"
                                        class="cursor-pointer transition-colors duration-150"
                                        :class="selectedId === item.id ? 'bg-rust-wash' : 'hover:bg-black/[0.01]'">
                                        <td class="px-4 py-3 font-mono text-[11px] whitespace-nowrap" x-text="formatDate(field(item, 'received_at'))"></td>
                                        <td class="px-4 py-3 text-xs font-sans font-bold" x-text="field(item, 'submitter') || 'Anonymous'"></td>
                                        <td class="px-4 py-3 text-xs font-serif text-forge-dark max-w-[240px] truncate" x-text="excerpt(item)"></td>
                                        <td class="px-4 py-3 text-[10px] font-black uppercase tracking-wider" x-text="field(item, 'kind')"></td>
                                        <td class="px-4 py-3 font-mono text-[11px]" x-text="field(item, 'parent_slug') || '—'"></td>
                                        <td class="px-4 py-3 text-[10px] font-black uppercase tracking-wider" x-text="itemStatus(item)"></td>
                                        <td class="px-4 py-3 text-[10px] font-mono" x-text="field(item, 'source_type') || '—'"></td>
                                    </tr>
                                </template>
                            </tbody>
                        </table>
                    </div>

                    <template x-if="!loading && filteredItems.length === 0">
                        <div class="text-center py-20 border border-dashed border-border bg-card">
                            <p class="text-forge-dark font-serif text-sm">No feedback matching the filters.</p>
                        </div>
                    </template>

                    <template x-if="loading">
                        <div class="flex justify-center py-20">
                            <span class="pen-spinner" role="status" aria-label="Loading…"></span>
                        </div>
                    </template>
                </div>

                <div x-show="selected" x-cloak class="pen-card p-6 bg-card space-y-4">
                    <h2 class="text-xs font-black uppercase tracking-wider text-forge-black">Detail</h2>
                    <p class="text-sm font-serif text-forge-black whitespace-pre-wrap" x-text="selected && selected.content"></p>
                    <dl class="space-y-2 text-xs">
                        <div x-show="selected && field(selected, 'email')">
                            <dt class="text-[9px] uppercase tracking-wider text-forge-mid font-bold">Email</dt>
                            <dd class="font-mono" x-text="selected && field(selected, 'email')"></dd>
                        </div>
                        <div x-show="selected && field(selected, 'source_url')">
                            <dt class="text-[9px] uppercase tracking-wider text-forge-mid font-bold">Source URL</dt>
                            <dd class="font-mono break-all" x-text="selected && field(selected, 'source_url')"></dd>
                        </div>
                        <div>
                            <dt class="text-[9px] uppercase tracking-wider text-forge-mid font-bold">Received</dt>
                            <dd class="font-mono" x-text="selected && formatDate(field(selected, 'received_at'))"></dd>
                        </div>
                    </dl>
                    <div class="flex flex-wrap items-end gap-3 pt-4 border-t border-border" x-show="$store.app.hasCap('write:pages')" x-cloak>
                        <div>
                            <label class="text-[9px] uppercase tracking-wider text-forge-mid font-bold block mb-1" for="feedback-status">Status</label>
                            <select id="feedback-status" x-model="editStatus" class="pen-input text-xs py-1.5 min-w-[140px]">
                                <option value="stub">stub</option>
                                <option value="draft">draft</option>
                                <option value="unpublished">unpublished</option>
                            </select>
                        </div>
                        <button type="button" @click="saveStatus()" :disabled="savingStatus" class="pen-btn pen-btn-secondary pen-btn-sm">
                            <span x-text="savingStatus ? 'Saving…' : 'Save status'"></span>
                        </button>
                    </div>
                    <div class="pt-2" x-show="$store.app.hasCap('delete:pages')" x-cloak>
                        <button type="button" @click="requestDelete(selected)" class="pen-btn pen-btn-danger pen-btn-sm">Delete</button>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <div x-show="deleteModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal-danger min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="deleteModalOpen = false" @keydown.escape.window="deleteModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Delete Feedback</h3>
                <button type="button" @click="deleteModalOpen = false" class="text-forge-mid hover:text-forge-black focus:outline-none">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    Confirm if you want to permanently delete<br>
                    <strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border" x-text="itemToDelete?.id"></strong>
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose">
                    This action is immediate, will remove the entry from database indexes, physically delete the markdown files from disk, and cannot be undone.
                </p>
            </div>
            <div class="pen-modal-footer">
                <button type="button" @click="deleteModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm focus:outline-none">Cancel</button>
                <button type="button" @click="confirmDelete()" class="pen-btn pen-btn-danger pen-btn-sm focus:outline-none">Delete</button>
            </div>
        </div>
    </div>

    <?php include "includes/_admin-footer.php"; ?>
