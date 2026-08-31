<?php
$pageTitle = "PenCMS Comments";
$currentSection = "comments";
$pageScript = "comments.js";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="commentsAdmin" x-init="init()">

    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <?php include "includes/_admin-sidebar.php"; ?>

        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">
            <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                <div>
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase"
                        x-text="pendingTotal > 0 ? `Comments: ${pendingTotal} new` : 'Comments'">
                        Comments
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        New reader comments, grouped by post.
                        <span class="text-forge-mid font-sans text-xs ml-1">Site: <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span></span>
                    </p>
                </div>
                <div class="flex-shrink-0 flex flex-col items-end gap-3">
                    <div class="flex items-center gap-3"
                         x-show="commentsFlagKnown && comments_enabled && $store.app.hasCap('write:seo')"
                         x-cloak>
                        <button type="button"
                                @click="toggleCommentsEnabled()"
                                class="pen-toggle"
                                :class="comments_enabled ? 'active' : ''"
                                role="switch"
                                :aria-checked="comments_enabled"
                                :disabled="savingCommentsEnabled"
                                id="comments_enabled_toggle">
                            <span class="pen-toggle-knob"></span>
                        </button>
                        <div class="flex flex-col">
                            <label @click="toggleCommentsEnabled()" class="font-sans font-bold text-xs uppercase tracking-wider text-forge-black cursor-pointer select-none" x-text="comments_enabled ? 'Reader comments on' : 'Comments off for this site'">
                            </label>
                            <span class="text-[10px] text-forge-mid leading-relaxed">
                                <span x-show="!comments_enabled">This site: click to enable reader comments</span>
                                <span x-show="comments_enabled" x-cloak>Comments enabled for this site</span>
                            </span>
                        </div>
                    </div>
                    <button type="button"
                            @click="pullFromRelay()"
                            x-show="commentsFlagKnown && comments_enabled && $store.app.hasCap('write:posts')"
                            x-cloak
                            :disabled="pulling"
                            class="pen-btn pen-btn-primary flex items-center gap-2">
                        <svg class="w-4 h-4" :class="pulling ? 'animate-spin' : ''" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                        </svg>
                        <span x-text="pulling ? 'Pulling…' : 'Pull from relay'"></span>
                    </button>
                </div>
            </div>

            <div x-show="pullBanner" x-cloak class="pen-card px-5 py-3 mb-6 flex items-center gap-3">
                <span class="text-[10px] font-bold uppercase tracking-widest"
                      :class="pullBanner && pullBanner.type === 'ok' ? 'text-rust' : 'text-forge-mid'">Result:</span>
                <span class="text-sm font-mono font-bold" x-text="pullBanner && pullBanner.message"></span>
            </div>

            <div x-show="commentsFlagKnown && !comments_enabled" x-cloak class="max-w-2xl space-y-6">
                <p class="text-forge-dark font-serif text-sm leading-relaxed">
                    Comments are <strong class="font-sans">optional</strong>. New sites start with comments off.
                    You can moderate reader comments here only after they are turned on for this site.
                </p>
                <p class="text-forge-black font-serif text-base leading-relaxed">
                    Comments are currently disabled for this site. Do you want to allow readers to leave public comments under each post?
                </p>
                <div class="flex flex-wrap items-center gap-3">
                    <button type="button"
                            @click="leaveWithoutChange()"
                            class="pen-btn pen-btn-secondary text-base px-8 py-3">
                        No change
                    </button>
                    <button type="button"
                            x-show="$store.app.hasCap('write:seo')"
                            x-cloak
                            @click="setCommentsEnabled(true)"
                            :disabled="savingCommentsEnabled"
                            class="pen-btn pen-btn-primary text-base px-8 py-3">
                        Turn on Comments
                    </button>
                </div>
            </div>

            <div x-show="commentsFlagKnown && comments_enabled" x-cloak>
                <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
                    <div class="flex flex-col gap-1 min-w-0 w-full sm:max-w-sm">
                        <label class="text-xs font-bold uppercase text-forge-mid" for="comments-post-slug">Post</label>
                        <select id="comments-post-slug" x-model="postSlug" @change="onPostChange()"
                                class="pen-input text-xs py-1.5">
                            <option value="">All posts</option>
                            <template x-for="page in postOptions" :key="page.id">
                                <option :value="page.id" x-text="postOptionLabel(page)"></option>
                            </template>
                        </select>
                    </div>
                    <div class="flex gap-1 overflow-x-auto scrollbar-none border-b border-border">
                        <template x-for="status in ['PENDING', 'VISIBLE', 'HIDDEN', 'ALL']" :key="status">
                            <button type="button" @click="setFilter(status)"
                                    class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150 whitespace-nowrap focus:outline-none"
                                    :class="filterVisibility === status ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                                <span x-text="status"></span>
                            </button>
                        </template>
                    </div>
                </div>

                <template x-if="loading">
                    <div class="flex justify-center py-20">
                        <span class="pen-spinner" role="status" aria-label="Loading…"></span>
                    </div>
                </template>

                <div x-show="!loading" class="space-y-10">
                    <!-- SECTION 1: FILTER TABS !== 'PENDING' (VISIBLE, HIDDEN, ALL) -->
                    <div x-show="filterVisibility !== 'PENDING'" class="space-y-8">
                        <div class="space-y-8" x-show="pagedGroups.length">
                            <template x-for="group in pagedGroups" :key="group.postSlug">
                                <section class="space-y-3">
                                    <div class="flex flex-wrap items-end justify-between gap-2 border-b border-border pb-2">
                                        <div class="min-w-0">
                                            <h2 class="text-sm font-sans font-black uppercase tracking-wide text-forge-black" x-text="groupTitle(group)"></h2>
                                            <p class="text-[10px] font-mono text-forge-mid" x-text="group.postSlug"></p>
                                        </div>
                                        <div class="flex items-center gap-3">
                                            <span class="text-[10px] font-bold uppercase tracking-widest text-forge-mid"
                                                  x-show="groupPendingBadge(group)"
                                                  x-cloak>
                                                <span class="text-rust font-mono" x-text="groupPendingBadge(group)"></span> pending
                                            </span>
                                            <a :href="previewUrlFor(group.postSlug)"
                                               target="_blank"
                                               rel="noopener noreferrer"
                                               class="text-[10px] font-bold uppercase tracking-widest text-rust hover:underline">
                                                View post
                                            </a>
                                        </div>
                                    </div>
                                    <div class="space-y-3">
                                        <template x-for="item in group.comments" :key="item.slug">
                                            <article class="pen-card bg-card p-5 space-y-3">
                                                <div class="flex flex-wrap items-baseline justify-between gap-2">
                                                    <div class="flex items-center gap-2 flex-wrap">
                                                        <span class="text-xs font-sans font-bold" x-text="item.author_name || 'Anonymous'"></span>
                                                        <span class="text-[10px] font-mono text-forge-mid" x-text="formatDate(item.received_at)"></span>
                                                        <!-- Source in parenthesis after dateline -->
                                                        <span class="text-[10px] font-mono text-forge-mid"
                                                              x-show="item.source_type"
                                                              x-cloak
                                                              x-text="'(' + item.source_type + ')'"></span>
                                                        <span x-show="item.author_kind === 'agent'"
                                                              x-cloak
                                                              class="inline-flex items-center p-1 bg-canvas border border-border rounded text-forge-mid"
                                                              title="Agent comment">
                                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-3.5 h-3.5" fill="currentColor"><rect width="256" height="256" fill="none"/><path d="M200,56H56A24,24,0,0,0,32,80V192a24,24,0,0,0,24,24H200a24,24,0,0,0,24-24V80A24,24,0,0,0,200,56ZM164,184H92a20,20,0,0,1,0-40h72a20,20,0,0,1,0,40Z" opacity="0.2"/><rect x="32" y="56" width="192" height="160" rx="24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="128" y1="56" x2="128" y2="16" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="84" cy="108" r="12"/><circle cx="172" cy="108" r="12"/><rect x="72" y="144" width="112" height="40" rx="20" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="148" y1="144" x2="148" y2="184" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="108" y1="144" x2="108" y2="184" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                                        </span>
                                                        <span class="text-[10px] font-mono text-forge-mid"
                                                              x-show="item.in_reply_to"
                                                              x-cloak
                                                              x-text="'reply to ' + item.in_reply_to"></span>
                                                    </div>
                                                    <div class="flex items-center gap-3">
                                                        <template x-if="item.visibility === 'visible'">
                                                            <span class="inline-flex items-center gap-1 text-[10px] font-black uppercase tracking-wider text-rust">
                                                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-3.5 h-3.5 text-rust flex-shrink-0" fill="none"><rect width="256" height="256" fill="none"/><path d="M54.46,201.54c-9.2-9.2-3.1-28.53-7.78-39.85C41.82,150,24,140.5,24,128s17.82-22,22.68-33.69C51.36,83,45.26,63.66,54.46,54.46S83,51.36,94.31,46.68C106.05,41.82,115.5,24,128,24S150,41.82,161.69,46.68c11.32,4.68,30.65-1.42,39.85,7.78s3.1,28.53,7.78,39.85C214.18,106.05,232,115.5,232,128S214.18,150,209.32,161.69c-4.68,11.32,1.42,30.65-7.78,39.85s-28.53,3.1-39.85,7.78C150,214.18,140.5,232,128,232s-22-17.82-33.69-22.68C83,204.64,63.66,210.74,54.46,201.54Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                                <span>Approved</span>
                                                            </span>
                                                        </template>
                                                        <template x-if="item.visibility !== 'visible'">
                                                            <span class="text-[10px] font-black uppercase tracking-wider"
                                                                  :class="visibilityClass(item.visibility)"
                                                                  x-text="item.visibility"></span>
                                                        </template>
                                                    </div>
                                                </div>
                                                <div class="text-sm font-serif text-forge-black whitespace-pre-wrap break-words"
                                                     x-show="editingSlug !== item.slug"
                                                     x-text="item.body"></div>
                                                <div class="space-y-3" x-show="editingSlug === item.slug" x-cloak>
                                                    <div>
                                                        <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1" :for="'edit-author-' + item.slug">Author</label>
                                                        <input type="text" class="pen-input text-xs py-1.5 w-full" x-model="editAuthor" :id="'edit-author-' + item.slug">
                                                    </div>
                                                    <div>
                                                        <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1" :for="'edit-body-' + item.slug">Comment</label>
                                                        <textarea class="pen-input text-sm font-serif min-h-[120px] w-full" x-model="editBody" :id="'edit-body-' + item.slug"></textarea>
                                                    </div>
                                                    <div class="flex flex-wrap items-center justify-end gap-2 pt-2">
                                                        <button type="button" class="pen-btn pen-btn-secondary pen-btn-sm"
                                                                @click="resetEditors()">Cancel</button>
                                                        <button type="button" class="pen-btn pen-btn-primary pen-btn-sm"
                                                                @click="submitEdit(item)"
                                                                :disabled="savingSlug === item.slug">Save</button>
                                                    </div>
                                                </div>
                                                <div class="space-y-3" x-show="replyingSlug === item.slug" x-cloak>
                                                    <div>
                                                        <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1" :for="'reply-body-' + item.slug">Reply (published with this comment)</label>
                                                        <textarea class="pen-input text-sm font-serif min-h-[100px] w-full" x-model="replyBody" :id="'reply-body-' + item.slug"></textarea>
                                                    </div>
                                                    <div class="flex flex-wrap items-center justify-end gap-2 pt-2">
                                                        <button type="button" class="pen-btn pen-btn-secondary pen-btn-sm"
                                                                @click="resetEditors()">Cancel</button>
                                                        <button type="button" class="pen-btn pen-btn-primary pen-btn-sm"
                                                                @click="submitReply(item)"
                                                                :disabled="savingSlug === item.slug">Approve and reply</button>
                                                    </div>
                                                </div>
                                                <div class="flex flex-wrap items-center gap-2"
                                                     x-show="editingSlug !== item.slug && replyingSlug !== item.slug">
                                                    <button type="button"
                                                            x-show="$store.app.hasCap('write:posts') && item.visibility !== 'visible'"
                                                            x-cloak
                                                            @click="setVisibility(item, 'visible')"
                                                            :disabled="savingSlug === item.slug"
                                                            class="pen-btn pen-btn-secondary pen-btn-sm">
                                                        Approve
                                                    </button>
                                                    <button type="button"
                                                            x-show="$store.app.hasCap('write:posts') && !item.in_reply_to"
                                                            x-cloak
                                                            @click="startReply(item)"
                                                            :disabled="savingSlug === item.slug"
                                                            class="pen-btn pen-btn-secondary pen-btn-sm">
                                                        Approve and reply
                                                    </button>
                                                    <button type="button"
                                                            x-show="$store.app.hasCap('write:posts')"
                                                            x-cloak
                                                            @click="startEdit(item)"
                                                            :disabled="savingSlug === item.slug"
                                                            class="pen-btn pen-btn-secondary pen-btn-sm">
                                                        Edit
                                                    </button>
                                                    <button type="button"
                                                            x-show="$store.app.hasCap('write:posts') && item.visibility !== 'hidden'"
                                                            x-cloak
                                                            @click="setVisibility(item, 'hidden')"
                                                            :disabled="savingSlug === item.slug"
                                                            class="pen-btn pen-btn-secondary pen-btn-sm">
                                                        Hide
                                                    </button>
                                                    <button type="button"
                                                            x-show="$store.app.hasCap('delete:posts')"
                                                            x-cloak
                                                            @click="requestDelete(item)"
                                                            class="pen-btn pen-btn-danger pen-btn-sm">
                                                        Delete
                                                    </button>
                                                </div>
                                            </article>
                                        </template>
                                    </div>
                                </section>
                            </template>
                        </div>

                        <div class="flex items-center justify-between gap-3 mt-6"
                             x-show="commentGroups.length > groupsPerPage">
                            <button type="button"
                                    class="pen-btn pen-btn-secondary pen-btn-sm"
                                    :disabled="groupPage <= 1"
                                    @click="groupPage = Math.max(1, groupPage - 1)">
                                Previous
                            </button>
                            <span class="text-[10px] font-mono text-forge-mid uppercase tracking-widest">
                                Page <span x-text="groupPage"></span> / <span x-text="groupPageCount"></span>
                            </span>
                            <button type="button"
                                    class="pen-btn pen-btn-secondary pen-btn-sm"
                                    :disabled="groupPage >= groupPageCount"
                                    @click="groupPage = Math.min(groupPageCount, groupPage + 1)">
                                Next
                            </button>
                        </div>

                        <div class="text-center py-20 border border-dashed border-border bg-card"
                             x-show="filteredComments.length === 0">
                            <p class="text-forge-dark font-serif text-sm">No comments matching the filters.</p>
                        </div>
                    </div>

                    <!-- SECTION 2: FILTER TAB === 'PENDING' (DEFAULT / FIRST PAGE) -->
                    <div x-show="filterVisibility === 'PENDING'" class="space-y-10">
                        <!-- Pending comments list (when pending comments exist) -->
                        <div x-show="pagedGroups.length" class="space-y-6">
                            <div class="flex items-center justify-between border-b-2 border-border-weld pb-2">
                                <div class="flex items-center gap-3">
                                    <h2 class="text-base font-sans font-black uppercase tracking-wide text-forge-black">
                                        New comments
                                    </h2>
                                    <span class="text-xs font-mono font-bold px-2 py-0.5 bg-rust-wash border border-rust text-rust rounded-sm"
                                          x-text="`${pendingTotal} pending`"></span>
                                </div>
                            </div>

                            <div class="space-y-8">
                                <template x-for="group in pagedGroups" :key="group.postSlug">
                                    <section class="space-y-3">
                                        <div class="flex flex-wrap items-end justify-between gap-2 border-b border-border pb-2">
                                            <div class="min-w-0">
                                                <h3 class="text-sm font-sans font-black uppercase tracking-wide text-forge-black" x-text="groupTitle(group)"></h3>
                                                <p class="text-[10px] font-mono text-forge-mid" x-text="group.postSlug"></p>
                                            </div>
                                            <div class="flex items-center gap-3">
                                                <span class="text-[10px] font-bold uppercase tracking-widest text-forge-mid"
                                                      x-show="groupPendingBadge(group)"
                                                      x-cloak>
                                                    <span class="text-rust font-mono" x-text="groupPendingBadge(group)"></span> pending
                                                </span>
                                                <a :href="previewUrlFor(group.postSlug)"
                                                   target="_blank"
                                                   rel="noopener noreferrer"
                                                   class="text-[10px] font-bold uppercase tracking-widest text-rust hover:underline">
                                                    View post
                                                </a>
                                            </div>
                                        </div>
                                        <div class="space-y-3">
                                            <template x-for="item in group.comments" :key="item.slug">
                                                <article class="pen-card bg-card p-5 space-y-3">
                                                    <div class="flex flex-wrap items-baseline justify-between gap-2">
                                                        <div class="flex items-center gap-2 flex-wrap">
                                                            <span class="text-xs font-sans font-bold" x-text="item.author_name || 'Anonymous'"></span>
                                                            <span class="text-[10px] font-mono text-forge-mid" x-text="formatDate(item.received_at)"></span>
                                                            <!-- Source in parenthesis after dateline -->
                                                            <span class="text-[10px] font-mono text-forge-mid"
                                                                  x-show="item.source_type"
                                                                  x-cloak
                                                                  x-text="'(' + item.source_type + ')'"></span>
                                                            <span x-show="item.author_kind === 'agent'"
                                                                  x-cloak
                                                                  class="inline-flex items-center p-1 bg-canvas border border-border rounded text-forge-mid"
                                                                  title="Agent comment">
                                                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-3.5 h-3.5" fill="currentColor"><rect width="256" height="256" fill="none"/><path d="M200,56H56A24,24,0,0,0,32,80V192a24,24,0,0,0,24,24H200a24,24,0,0,0,24-24V80A24,24,0,0,0,200,56ZM164,184H92a20,20,0,0,1,0-40h72a20,20,0,0,1,0,40Z" opacity="0.2"/><rect x="32" y="56" width="192" height="160" rx="24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="128" y1="56" x2="128" y2="16" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="84" cy="108" r="12"/><circle cx="172" cy="108" r="12"/><rect x="72" y="144" width="112" height="40" rx="20" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="148" y1="144" x2="148" y2="184" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="108" y1="144" x2="108" y2="184" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                                            </span>
                                                            <span class="text-[10px] font-mono text-forge-mid"
                                                                  x-show="item.in_reply_to"
                                                                  x-cloak
                                                                  x-text="'reply to ' + item.in_reply_to"></span>
                                                        </div>
                                                        <div class="flex items-center gap-3">
                                                            <template x-if="item.visibility === 'visible'">
                                                                <span class="inline-flex items-center gap-1 text-[10px] font-black uppercase tracking-wider text-rust">
                                                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-3.5 h-3.5 text-rust flex-shrink-0" fill="none"><rect width="256" height="256" fill="none"/><path d="M54.46,201.54c-9.2-9.2-3.1-28.53-7.78-39.85C41.82,150,24,140.5,24,128s17.82-22,22.68-33.69C51.36,83,45.26,63.66,54.46,54.46S83,51.36,94.31,46.68C106.05,41.82,115.5,24,128,24S150,41.82,161.69,46.68c11.32,4.68,30.65-1.42,39.85,7.78s3.1,28.53,7.78,39.85C214.18,106.05,232,115.5,232,128S214.18,150,209.32,161.69c-4.68,11.32,1.42,30.65-7.78,39.85s-28.53,3.1-39.85,7.78C150,214.18,140.5,232,128,232s-22-17.82-33.69-22.68C83,204.64,63.66,210.74,54.46,201.54Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                                    <span>Approved</span>
                                                                </span>
                                                            </template>
                                                            <template x-if="item.visibility !== 'visible'">
                                                                <span class="text-[10px] font-black uppercase tracking-wider"
                                                                      :class="visibilityClass(item.visibility)"
                                                                      x-text="item.visibility"></span>
                                                            </template>
                                                        </div>
                                                    </div>
                                                    <div class="text-sm font-serif text-forge-black whitespace-pre-wrap break-words"
                                                         x-show="editingSlug !== item.slug"
                                                         x-text="item.body"></div>
                                                    <div class="space-y-3" x-show="editingSlug === item.slug" x-cloak>
                                                        <div>
                                                            <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1" :for="'edit-author-' + item.slug">Author</label>
                                                            <input type="text" class="pen-input text-xs py-1.5 w-full" x-model="editAuthor" :id="'edit-author-' + item.slug">
                                                        </div>
                                                        <div>
                                                            <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1" :for="'edit-body-' + item.slug">Comment</label>
                                                            <textarea class="pen-input text-sm font-serif min-h-[120px] w-full" x-model="editBody" :id="'edit-body-' + item.slug"></textarea>
                                                        </div>
                                                        <div class="flex flex-wrap items-center justify-end gap-2 pt-2">
                                                            <button type="button" class="pen-btn pen-btn-secondary pen-btn-sm"
                                                                    @click="resetEditors()">Cancel</button>
                                                            <button type="button" class="pen-btn pen-btn-primary pen-btn-sm"
                                                                    @click="submitEdit(item)"
                                                                    :disabled="savingSlug === item.slug">Save</button>
                                                        </div>
                                                    </div>
                                                    <div class="space-y-3" x-show="replyingSlug === item.slug" x-cloak>
                                                        <div>
                                                            <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1" :for="'reply-body-' + item.slug">Reply (published with this comment)</label>
                                                            <textarea class="pen-input text-sm font-serif min-h-[100px] w-full" x-model="replyBody" :id="'reply-body-' + item.slug"></textarea>
                                                        </div>
                                                        <div class="flex flex-wrap items-center justify-end gap-2 pt-2">
                                                            <button type="button" class="pen-btn pen-btn-secondary pen-btn-sm"
                                                                    @click="resetEditors()">Cancel</button>
                                                            <button type="button" class="pen-btn pen-btn-primary pen-btn-sm"
                                                                    @click="submitReply(item)"
                                                                    :disabled="savingSlug === item.slug">Approve and reply</button>
                                                        </div>
                                                    </div>
                                                    <div class="flex flex-wrap items-center gap-2"
                                                         x-show="editingSlug !== item.slug && replyingSlug !== item.slug">
                                                        <button type="button"
                                                                x-show="$store.app.hasCap('write:posts') && item.visibility !== 'visible'"
                                                                x-cloak
                                                                @click="setVisibility(item, 'visible')"
                                                                :disabled="savingSlug === item.slug"
                                                                class="pen-btn pen-btn-secondary pen-btn-sm">
                                                            Approve
                                                        </button>
                                                        <button type="button"
                                                                x-show="$store.app.hasCap('write:posts') && !item.in_reply_to"
                                                                x-cloak
                                                                @click="startReply(item)"
                                                                :disabled="savingSlug === item.slug"
                                                                class="pen-btn pen-btn-secondary pen-btn-sm">
                                                            Approve and reply
                                                        </button>
                                                        <button type="button"
                                                                x-show="$store.app.hasCap('write:posts')"
                                                                x-cloak
                                                                @click="startEdit(item)"
                                                                :disabled="savingSlug === item.slug"
                                                                class="pen-btn pen-btn-secondary pen-btn-sm">
                                                            Edit
                                                        </button>
                                                        <button type="button"
                                                                x-show="$store.app.hasCap('write:posts') && item.visibility !== 'hidden'"
                                                                x-cloak
                                                                @click="setVisibility(item, 'hidden')"
                                                                :disabled="savingSlug === item.slug"
                                                                class="pen-btn pen-btn-secondary pen-btn-sm">
                                                            Hide
                                                        </button>
                                                        <button type="button"
                                                                x-show="$store.app.hasCap('delete:posts')"
                                                                x-cloak
                                                                @click="requestDelete(item)"
                                                                class="pen-btn pen-btn-danger pen-btn-sm">
                                                            Delete
                                                        </button>
                                                    </div>
                                                </article>
                                            </template>
                                        </div>
                                    </section>
                                </template>
                            </div>

                            <div class="flex items-center justify-between gap-3 mt-6"
                                 x-show="commentGroups.length > groupsPerPage">
                                <button type="button"
                                        class="pen-btn pen-btn-secondary pen-btn-sm"
                                        :disabled="groupPage <= 1"
                                        @click="groupPage = Math.max(1, groupPage - 1)">
                                    Previous
                                </button>
                                <span class="text-[10px] font-mono text-forge-mid uppercase tracking-widest">
                                    Page <span x-text="groupPage"></span> / <span x-text="groupPageCount"></span>
                                </span>
                                <button type="button"
                                        class="pen-btn pen-btn-secondary pen-btn-sm"
                                        :disabled="groupPage >= groupPageCount"
                                        @click="groupPage = Math.min(groupPageCount, groupPage + 1)">
                                    Next
                                </button>
                            </div>
                        </div>

                        <!-- Notice when 0 pending comments, but recent comment history exists -->
                        <div x-show="filteredComments.length === 0 && latestComments.length > 0"
                             class="p-4 bg-card border border-border flex items-center justify-between shadow-sm">
                            <div class="flex items-center gap-2.5">
                                <svg class="w-4 h-4 text-rust flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                                </svg>
                                <span class="text-xs font-sans font-bold text-forge-black">No new comments to moderate.</span>
                                <span class="text-xs font-serif text-forge-dark">Showing recent comment history below.</span>
                            </div>
                        </div>

                        <!-- DIGEST: LATEST COMMENTS (Always shown on first page / PENDING tab when latest comments exist) -->
                        <div x-show="latestComments.length > 0" class="space-y-4">
                            <div class="flex items-center justify-between border-b-2 border-border-weld pb-2">
                                <div class="flex items-center gap-3">
                                    <h2 class="text-base font-sans font-black uppercase tracking-wide text-forge-black">
                                        Latest comments
                                    </h2>
                                    <span class="text-xs font-mono font-bold px-2 py-0.5 bg-canvas border border-border text-forge-mid rounded-sm"
                                          x-text="`${latestComments.length} total`"></span>
                                </div>
                            </div>

                            <!-- The Digest List -->
                            <div class="border border-border bg-card divide-y divide-border shadow-sm">
                                <template x-for="item in pagedLatestComments" :key="item.slug">
                                    <div class="transition-colors duration-150"
                                         :class="[
                                             expandedDigestSlug === item.slug ? 'bg-rust-wash/25' : (item.visibility === 'hidden' ? 'bg-black/[0.015] hover:bg-black/[0.03]' : 'hover:bg-black/[0.015]')
                                         ]">
                                        
                                        <!-- One line Digest Row -->
                                        <div class="flex flex-col sm:flex-row sm:items-center justify-between px-4 py-2.5 gap-2 sm:gap-3 cursor-pointer select-none"
                                             @click="toggleDigest(item)"
                                             role="button"
                                             :aria-expanded="expandedDigestSlug === item.slug"
                                             tabindex="0"
                                             @keydown.enter.prevent="toggleDigest(item)"
                                             @keydown.space.prevent="toggleDigest(item)">
                                            
                                            <!-- Left content: Date - Name - Comment Text -->
                                            <div class="flex items-center gap-2 sm:gap-3 min-w-0 flex-1 overflow-hidden">
                                                
                                                <!-- Date (Clean, readable, no strikethrough) -->
                                                <span class="font-mono text-[11px] whitespace-nowrap flex-shrink-0 w-[110px] text-forge-mid"
                                                      x-text="formatDigestDate(item.received_at)"></span>
                                                
                                                <span class="text-forge-mid text-xs flex-shrink-0" aria-hidden="true">-</span>
                                                
                                                <!-- Name + optional reply tag (Struck through if hidden) -->
                                                <div class="flex items-center gap-1.5 flex-shrink-0 w-[130px] sm:w-[150px] md:w-[160px] min-w-0">
                                                    <span class="font-sans font-bold text-xs truncate"
                                                          :class="item.visibility === 'hidden' ? 'line-through text-forge-mid opacity-75' : 'text-forge-black'"
                                                          x-text="item.author_name || 'Anonymous'"></span>
                                                    <span x-show="item.in_reply_to" x-cloak
                                                          class="inline-flex items-center gap-1 text-[9px] font-mono uppercase px-1 py-0.5 bg-canvas border border-border text-forge-mid rounded flex-shrink-0">
                                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-2.5 h-2.5 text-forge-mid flex-shrink-0" fill="none"><rect width="256" height="256" fill="none"/><polyline points="88 152 24 152 24 88" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M224,184A96,96,0,0,0,60.12,116.12L24,152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                        <span>reply</span>
                                                    </span>
                                                </div>
                                                
                                                <span class="text-forge-mid text-xs flex-shrink-0" aria-hidden="true">-</span>
                                                
                                                <!-- Comment text (Struck through if hidden, truncated 200 chars) -->
                                                <div class="font-serif text-xs min-w-0 flex-1 truncate"
                                                     :class="item.visibility === 'hidden' ? 'line-through text-forge-mid opacity-75' : 'text-forge-dark'"
                                                     x-text="truncateText(item.body, 200)"
                                                     :title="item.body"></div>
                                            </div>
                                            
                                            <!-- Right content: Status icon (acts as separator) Post name - Chevron -->
                                            <div class="flex items-center gap-3 flex-shrink-0 justify-between sm:justify-end text-right sm:text-left">
                                                
                                                <!-- Status icon (double-duty separator) -->
                                                <div class="flex items-center justify-center w-5 flex-shrink-0">
                                                    <!-- Visible primary comment -->
                                                    <template x-if="item.visibility === 'visible' && !item.in_reply_to">
                                                        <span class="inline-flex items-center flex-shrink-0" title="Visible comment">
                                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4 text-rust flex-shrink-0" fill="none"><rect width="256" height="256" fill="none"/><path d="M45.15,230.11A8,8,0,0,1,32,224V64a8,8,0,0,1,8-8H216a8,8,0,0,1,8,8V192a8,8,0,0,1-8,8H80Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="96" y1="108" x2="160" y2="108" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="96" y1="148" x2="160" y2="148" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                        </span>
                                                    </template>
                                                    <!-- Visible reply comment -->
                                                    <template x-if="item.visibility === 'visible' && item.in_reply_to">
                                                        <span class="inline-flex items-center flex-shrink-0" title="Visible reply">
                                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4 text-rust flex-shrink-0" fill="none"><rect width="256" height="256" fill="none"/><path d="M71.58,144,32,176V48a8,8,0,0,1,8-8H168a8,8,0,0,1,8,8v88a8,8,0,0,1-8,8Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M80,144v40a8,8,0,0,0,8,8h96.42L224,224V96a8,8,0,0,0-8-8H176" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                        </span>
                                                    </template>
                                                    <!-- Hidden comment (dark red slashed circle, no strikethrough) -->
                                                    <template x-if="item.visibility === 'hidden'">
                                                        <span class="inline-flex items-center flex-shrink-0" title="Hidden comment">
                                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4 text-danger flex-shrink-0" fill="currentColor"><rect width="256" height="256" fill="none"/><path d="M200,128a71.69,71.69,0,0,1-15.78,44.91L83.09,71.78A71.95,71.95,0,0,1,200,128ZM56,128a71.95,71.95,0,0,0,116.91,56.22L71.78,83.09A71.69,71.69,0,0,0,56,128Zm180,0A108,108,0,1,1,128,20,108.12,108.12,0,0,1,236,128Zm-20,0a88,88,0,1,0-88,88A88.1,88.1,0,0,0,216,128Z"/></svg>
                                                        </span>
                                                    </template>
                                                </div>
                                                
                                                <!-- Post name (Clean, readable, no strikethrough, truncated 50 chars) -->
                                                <div class="font-sans font-bold text-[11px] text-forge-mid w-[140px] sm:w-[170px] md:w-[210px] truncate"
                                                     :title="postNameFor(item.post_slug)"
                                                     x-text="truncateText(postNameFor(item.post_slug), 50)"></div>
                                                
                                                <!-- Chevron toggle -->
                                                <svg class="w-4 h-4 text-forge-mid transition-transform duration-200"
                                                     :class="expandedDigestSlug === item.slug ? 'rotate-180 text-rust' : ''"
                                                     fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
                                                </svg>
                                            </div>
                                        </div>
                                        
                                        <!-- Accordion Drawer (Expanded Body) -->
                                        <div x-show="expandedDigestSlug === item.slug"
                                             x-cloak
                                             x-transition:enter="transition ease-out duration-150"
                                             x-transition:enter-start="opacity-0 -translate-y-1"
                                             x-transition:enter-end="opacity-100 translate-y-0"
                                             x-transition:leave="transition ease-in duration-100"
                                             x-transition:leave-start="opacity-100 translate-y-0"
                                             x-transition:leave-end="opacity-0 -translate-y-1"
                                             class="border-t border-border-weld bg-canvas/40 px-5 py-4 space-y-4">
                                            
                                            <!-- Drawer Meta Info Header -->
                                            <div class="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
                                                <div class="flex items-center gap-2 flex-wrap">
                                                    <span class="text-xs font-sans font-bold text-forge-black" x-text="item.author_name || 'Anonymous'"></span>
                                                    <span class="text-[10px] font-mono text-forge-mid" x-text="formatDate(item.received_at)"></span>
                                                    <!-- Source in parenthesis after dateline -->
                                                    <span class="text-[10px] font-mono text-forge-mid"
                                                          x-show="item.source_type"
                                                          x-cloak
                                                          x-text="'(' + item.source_type + ')'"></span>
                                                    <!-- Agent Icon Badge (only for agent comments) -->
                                                    <span x-show="item.author_kind === 'agent'"
                                                          x-cloak
                                                          class="inline-flex items-center p-1 bg-canvas border border-border rounded text-forge-mid"
                                                          title="Agent comment">
                                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-3.5 h-3.5" fill="currentColor"><rect width="256" height="256" fill="none"/><path d="M200,56H56A24,24,0,0,0,32,80V192a24,24,0,0,0,24,24H200a24,24,0,0,0,24-24V80A24,24,0,0,0,200,56ZM164,184H92a20,20,0,0,1,0-40h72a20,20,0,0,1,0,40Z" opacity="0.2"/><rect x="32" y="56" width="192" height="160" rx="24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="128" y1="56" x2="128" y2="16" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="84" cy="108" r="12"/><circle cx="172" cy="108" r="12"/><rect x="72" y="144" width="112" height="40" rx="20" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="148" y1="144" x2="148" y2="184" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="108" y1="144" x2="108" y2="184" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                                    </span>
                                                    <span class="text-[10px] font-mono text-forge-mid"
                                                          x-show="item.in_reply_to"
                                                          x-cloak
                                                          x-text="'reply to ' + item.in_reply_to"></span>
                                                </div>
                                                <div class="flex items-center gap-3">
                                                    <!-- Approved status when visible -->
                                                    <template x-if="item.visibility === 'visible'">
                                                        <span class="inline-flex items-center gap-1 text-[10px] font-black uppercase tracking-wider text-rust">
                                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-3.5 h-3.5 text-rust flex-shrink-0" fill="none"><rect width="256" height="256" fill="none"/><path d="M54.46,201.54c-9.2-9.2-3.1-28.53-7.78-39.85C41.82,150,24,140.5,24,128s17.82-22,22.68-33.69C51.36,83,45.26,63.66,54.46,54.46S83,51.36,94.31,46.68C106.05,41.82,115.5,24,128,24S150,41.82,161.69,46.68c11.32,4.68,30.65-1.42,39.85,7.78s3.1,28.53,7.78,39.85C214.18,106.05,232,115.5,232,128S214.18,150,209.32,161.69c-4.68,11.32,1.42,30.65-7.78,39.85s-28.53,3.1-39.85,7.78C150,214.18,140.5,232,128,232s-22-17.82-33.69-22.68C83,204.64,63.66,210.74,54.46,201.54Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                            <span>Approved</span>
                                                        </span>
                                                    </template>
                                                    <template x-if="item.visibility !== 'visible'">
                                                        <span class="text-[10px] font-black uppercase tracking-wider"
                                                              :class="visibilityClass(item.visibility)"
                                                              x-text="item.visibility"></span>
                                                    </template>
                                                    <a :href="previewUrlFor(item.post_slug)"
                                                       target="_blank"
                                                       rel="noopener noreferrer"
                                                       class="inline-flex items-center text-rust hover:text-rust-deep transition-colors"
                                                       title="Open post in new tab">
                                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4 text-rust" fill="none"><rect width="256" height="256" fill="none"/><line x1="136" y1="120" x2="216" y2="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><polyline points="216 104 215.99 40.01 152 40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M184,140v68a8,8,0,0,1-8,8H48a8,8,0,0,1-8-8V80a8,8,0,0,1,8-8h68" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                    </a>
                                                </div>
                                            </div>
                                            
                                            <!-- Drawer Body text -->
                                            <div class="text-sm font-serif text-forge-black whitespace-pre-wrap break-words leading-relaxed"
                                                 x-show="editingSlug !== item.slug"
                                                 x-text="item.body"></div>
                                            
                                            <!-- Drawer Edit Form -->
                                            <div class="space-y-3" x-show="editingSlug === item.slug" x-cloak>
                                                <div>
                                                    <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1" :for="'edit-digest-author-' + item.slug">Author</label>
                                                    <input type="text" class="pen-input text-xs py-1.5 w-full" x-model="editAuthor" :id="'edit-digest-author-' + item.slug">
                                                </div>
                                                <div>
                                                    <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1" :for="'edit-digest-body-' + item.slug">Comment</label>
                                                    <textarea class="pen-input text-sm font-serif min-h-[120px] w-full" x-model="editBody" :id="'edit-digest-body-' + item.slug"></textarea>
                                                </div>
                                                <div class="flex flex-wrap items-center justify-end gap-2 pt-2">
                                                    <button type="button" class="pen-btn pen-btn-secondary pen-btn-sm"
                                                            @click="resetEditors()">Cancel</button>
                                                    <button type="button" class="pen-btn pen-btn-primary pen-btn-sm"
                                                            @click="submitEdit(item)"
                                                            :disabled="savingSlug === item.slug">Save</button>
                                                </div>
                                            </div>
                                            
                                            <!-- Drawer Reply Form -->
                                            <div class="space-y-3" x-show="replyingSlug === item.slug" x-cloak>
                                                <div>
                                                    <label class="block text-[10px] font-bold uppercase tracking-wider text-forge-mid mb-1" :for="'reply-digest-body-' + item.slug">Reply (published with this comment)</label>
                                                    <textarea class="pen-input text-sm font-serif min-h-[100px] w-full" x-model="replyBody" :id="'reply-digest-body-' + item.slug"></textarea>
                                                </div>
                                                <div class="flex flex-wrap items-center justify-end gap-2 pt-2">
                                                    <button type="button" class="pen-btn pen-btn-secondary pen-btn-sm"
                                                            @click="resetEditors()">Cancel</button>
                                                    <button type="button" class="pen-btn pen-btn-primary pen-btn-sm"
                                                            @click="submitReply(item)"
                                                            :disabled="savingSlug === item.slug">Approve and reply</button>
                                                </div>
                                            </div>
                                            
                                            <!-- Drawer Action Buttons -->
                                            <div class="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-border"
                                                 x-show="editingSlug !== item.slug && replyingSlug !== item.slug">
                                                <button type="button"
                                                        x-show="$store.app.hasCap('delete:posts')"
                                                        x-cloak
                                                        @click="requestDelete(item)"
                                                        class="pen-btn pen-btn-secondary pen-btn-sm">
                                                    Delete
                                                </button>
                                                <button type="button"
                                                        x-show="$store.app.hasCap('write:posts') && item.visibility === 'visible'"
                                                        x-cloak
                                                        @click="setVisibility(item, 'hidden')"
                                                        :disabled="savingSlug === item.slug"
                                                        class="pen-btn pen-btn-secondary pen-btn-sm">
                                                    Hide
                                                </button>
                                                <button type="button"
                                                        x-show="$store.app.hasCap('write:posts') && item.visibility === 'hidden'"
                                                        x-cloak
                                                        @click="setVisibility(item, 'visible')"
                                                        :disabled="savingSlug === item.slug"
                                                        class="pen-btn pen-btn-secondary pen-btn-sm">
                                                    Approve
                                                </button>
                                                <button type="button"
                                                        x-show="$store.app.hasCap('write:posts') && !item.in_reply_to"
                                                        x-cloak
                                                        @click="startReply(item)"
                                                        :disabled="savingSlug === item.slug"
                                                        class="pen-btn pen-btn-secondary pen-btn-sm">
                                                    Approve and reply
                                                </button>
                                                <button type="button"
                                                        x-show="$store.app.hasCap('write:posts')"
                                                        x-cloak
                                                        @click="startEdit(item)"
                                                        :disabled="savingSlug === item.slug"
                                                        class="pen-btn pen-btn-primary pen-btn-sm">
                                                    Edit
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </template>
                            </div>

                            <!-- "SHOW MORE" Link -->
                            <div class="text-center py-3" x-show="latestComments.length > digestLimit">
                                <button type="button"
                                        @click="showMoreDigest()"
                                        class="text-xs font-sans font-bold uppercase tracking-widest text-rust hover:underline focus:outline-none py-2.5 px-6 border border-rust/30 hover:border-rust rounded bg-card hover:bg-rust-wash/30 transition-all shadow-sm">
                                    SHOW MORE
                                </button>
                            </div>
                        </div>

                        <!-- If NO comments exist at all (0 pending and 0 latest) -->
                        <div class="text-center py-20 border border-dashed border-border bg-card"
                             x-show="filteredComments.length === 0 && latestComments.length === 0">
                            <p class="text-forge-dark font-serif text-sm">No new comments.</p>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <div x-show="comments_enabled && deleteModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal-danger min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="deleteModalOpen = false" @keydown.escape.window="deleteModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Delete Comment</h3>
                <button type="button" @click="deleteModalOpen = false" class="text-forge-mid hover:text-forge-black focus:outline-none">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    Confirm if you want to permanently delete<br>
                    <strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border" x-text="itemToDelete?.slug"></strong>
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose">
                    This removes the comment file from disk. Git history remains. The contact inbox is unchanged.
                </p>
            </div>
            <div class="pen-modal-footer">
                <button type="button" @click="deleteModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm focus:outline-none">Cancel</button>
                <button type="button" @click="confirmDelete()" class="pen-btn pen-btn-danger pen-btn-sm focus:outline-none">Delete</button>
            </div>
        </div>
    </div>

    <?php include "includes/_admin-footer.php"; ?>
