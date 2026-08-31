<?php
$pageTitle = "Publish (PenCMS)";
$currentSection = "publish";
$pageScript = "publish.js";
include "includes/_admin-auth.php";

// Handle AJAX build request (streaming export pipeline)
if (isset($_GET["ajax_build"])) {
    $hasProcOpen = function_exists("proc_open");

    // Disable caching and buffering
    if (function_exists("apache_setenv")) {
        @apache_setenv("no-gzip", 1);
    }
    @ini_set("zlib.output_compression", 0);
    @ini_set("implicit_flush", 1);
    while (ob_get_level()) {
        ob_end_flush();
    }
    ob_implicit_flush(true);

    if (!$hasProcOpen) {
        echo "ERR: proc_open() is disabled in your PHP configuration.\n";
        exit();
    }

    $fullScriptPath = realpath(__DIR__ . "/../../cli-tools/build.sh");
    $exists = $fullScriptPath && file_exists($fullScriptPath);
    $readable = $exists && is_readable($fullScriptPath);

    if (!$readable) {
        echo "ERR: Build script not found or not readable.\n";
        exit();
    }

    $domain = trim($_GET["domain"] ?? "");
    $site = trim($_GET["site"] ?? "");
    $allSites = isset($_GET["all_sites"]) && $_GET["all_sites"] === "1";

    $command =
        "bash " .
        escapeshellarg($fullScriptPath) .
        " --domain " .
        escapeshellarg($domain);
    if ($allSites) {
        $command .= " --all-sites";
    } elseif ($site !== "") {
        $command .= " --site=" . escapeshellarg($site);
    }

    $env = $_ENV;
    $env["PATH"] =
        getenv("PATH") ?:
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin";
    if (isset($_SERVER["HTTP_X_VAULT_CONTENT_PASS"])) {
        $env["VAULT_CONTENT_PASS"] = $_SERVER["HTTP_X_VAULT_CONTENT_PASS"];
    }
    if (isset($_SERVER["HTTP_X_VAULT_ASSETS_PASS"])) {
        $env["VAULT_ASSETS_PASS"] = $_SERVER["HTTP_X_VAULT_ASSETS_PASS"];
    }

    $descriptorspec = [
        0 => ["pipe", "r"], // stdin
        1 => ["pipe", "w"], // stdout
        2 => ["pipe", "w"], // stderr
    ];

    $process = proc_open(
        $command,
        $descriptorspec,
        $pipes,
        dirname($fullScriptPath),
        $env,
    );

    if (is_resource($process)) {
        stream_set_blocking($pipes[1], 0);
        stream_set_blocking($pipes[2], 0);

        while (true) {
            $read = [$pipes[1], $pipes[2]];
            $write = null;
            $except = null;

            if (stream_select($read, $write, $except, 1) > 0) {
                foreach ($read as $pipe) {
                    while ($line = fgets($pipe)) {
                        $isError = $pipe === $pipes[2];
                        $prefix = $isError ? "ERR: " : "";
                        echo $prefix . $line;
                        echo str_repeat(" ", 4096); // Force flush
                        flush();
                    }
                }
            }

            $status = proc_get_status($process);
            if (!$status["running"]) {
                break;
            }
        }

        fclose($pipes[0]);
        fclose($pipes[1]);
        fclose($pipes[2]);
        $return_value = proc_close($process);

        echo "\n[PROCESS_EXIT:" . $return_value . "]\n";
        echo str_repeat(" ", 4096);
        flush();
    } else {
        echo "ERR: Failed to initialize proc_open.\n";
    }
    exit();
}

include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="publishPage">

    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <?php include "includes/_admin-sidebar.php"; ?>

        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">
            <div class="mb-8">
                <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                    Publish
                </h1>
                <p class="text-forge-dark font-serif text-sm">
                    Deploy to a connected host, export a static build, and manage publishing settings.
                    <span class="text-forge-mid font-sans text-xs ml-1">Site: <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span></span>
                </p>
            </div>

            <!-- Vault Unlock Modal -->
            <div x-show="showVaultModal" x-cloak class="fixed inset-0 bg-forge-black/80 z-50 flex items-center justify-center" @click.self="cancelVaultUnlock()">
                <div class="bg-card border-4 border-border-weld p-8 max-w-md w-full mx-4">
                    <h3 class="font-sans font-black uppercase text-sm tracking-wider mb-1">Vault Locked</h3>
                    <p class="text-xs text-forge-mid font-serif mb-6">Please enter your Master Password to continue.</p>
                    <form autocomplete="off" @submit.prevent="unlockVaultAndContinue()" class="space-y-4">
                        <div>
                            <label class="pen-label">Master Password</label>
                            <input type="password" x-model="vaultPassword" class="pen-input w-full" placeholder="Enter your Master Password" autocomplete="off" autofocus>
                            <p x-show="vaultError" x-text="vaultError" class="text-[10px] text-danger font-bold font-sans uppercase tracking-wider mt-1.5"></p>
                        </div>
                        <div class="flex justify-end gap-3 pt-2">
                            <button type="button" @click="cancelVaultUnlock()" class="pen-btn">Cancel</button>
                            <button type="submit" class="pen-btn-primary">Unlock &amp; Continue</button>
                        </div>
                    </form>
                </div>
            </div>

            <div class="flex border-b border-border mb-8 gap-1">
                <button type="button" @click="activeTab = 'publish'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'publish' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Publish
                </button>
                <button type="button" @click="activeTab = 'export'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'export' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Export
                </button>
                <button type="button" @click="activeTab = 'settings'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'settings' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Settings
                </button>
            </div>

            <div x-show="loading" class="text-sm font-serif text-forge-mid mb-6">Loading publish target…</div>

            <!-- Tab: Publish -->
            <div x-show="activeTab === 'publish' && !loading" class="space-y-8 max-w-4xl">
                <!-- Connected host hero -->
                <div x-show="configured" class="pen-card p-8 bg-card">
                    <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-6">
                        <div class="min-w-0 flex-1">
                            <p class="text-[10px] font-sans font-bold uppercase tracking-widest text-forge-mid mb-2">Deploy target</p>
                            <h2 class="text-2xl font-sans font-black uppercase tracking-tight text-primary mb-3">
                                Publish to <span class="text-rust" x-text="host"></span>
                            </h2>
                            <div class="flex flex-wrap items-center gap-3 mb-6">
                                <span class="inline-flex items-center gap-1.5 px-2 py-1 border border-acid/40 bg-acid-wash text-acid-text text-[10px] font-sans font-bold uppercase tracking-wider">
                                    <span class="w-1.5 h-1.5 rounded-full bg-acid"></span>
                                    Host configured
                                </span>
                                <span x-show="displayLastStatus"
                                      class="inline-flex items-center gap-1.5 px-2 py-1 border text-[10px] font-sans font-bold uppercase tracking-wider"
                                      :class="last_status === 'ok'
                                        ? 'border-acid/40 bg-acid-wash text-acid-text'
                                        : (last_status === 'failed'
                                          ? 'border-danger/40 bg-danger/10 text-danger'
                                          : 'border-border bg-canvas text-forge-mid')"
                                      x-text="'Status: ' + displayLastStatus"></span>
                                <span class="text-xs font-serif text-forge-dark">
                                    Last published:
                                    <span class="font-mono font-bold text-forge-black" x-text="displayLastPublished"></span>
                                </span>
                            </div>
                            <template x-if="displayLiveUrl">
                                <div>
                                    <p class="text-sm font-serif text-forge-dark mb-1">Live URL</p>
                                    <a :href="displayLiveUrl" target="_blank" rel="noopener"
                                       class="font-mono text-sm text-rust hover:text-rust-deep break-all"
                                       x-text="displayLiveUrl"></a>
                                </div>
                            </template>
                            <p x-show="!displayLiveUrl" class="text-sm font-serif text-forge-mid">No public URL set.</p>
                        </div>
                        <div class="flex-shrink-0 flex flex-col items-stretch gap-2">
                            <button type="button"
                                    @click="startPublish()"
                                    :disabled="!canHostPublish || !configured || publishing"
                                    class="pen-btn-primary text-base px-8 py-3"
                                    :class="(!canHostPublish || !configured || publishing) ? 'opacity-60 cursor-not-allowed' : ''"
                                    :title="!canHostPublish ? 'Requires publish' : (publishing ? 'Publish in progress' : 'Build and upload to host')">
                                <span x-text="publishing ? 'Publishing…' : 'Publish'"></span>
                            </button>
                            <label class="flex items-center gap-2 cursor-pointer select-none"
                                   :class="(!canHostPublish || !configured || publishing) ? 'opacity-60' : ''">
                                <input type="checkbox"
                                       x-model="forceFullUpload"
                                       :disabled="!canHostPublish || !configured || publishing"
                                       class="rounded border-border text-rust focus:ring-rust/40">
                                <span class="text-xs font-serif text-forge-dark">Force full upload</span>
                            </label>
                            <p x-show="publishing"
                               class="text-[10px] font-sans uppercase tracking-wider text-forge-mid text-center"
                               x-text="publishPhaseLabel"></p>
                        </div>
                    </div>
                </div>

                <!-- Publish progress / errors -->
                <div x-show="configured && (publishing || publishLog.length || publishStatus || publishError)"
                     x-cloak class="space-y-3">
                    <div x-show="publishError" class="border border-danger/40 bg-danger/10 px-4 py-3 space-y-2">
                        <p class="text-sm font-serif text-danger" x-text="publishError"></p>
                        <p x-show="publishHint" class="text-xs font-serif text-forge-dark" x-text="publishHint"></p>
                        <div class="flex flex-wrap items-center gap-3 pt-1">
                            <button type="button" @click="activeTab = 'settings'" class="pen-btn-secondary pen-btn-sm">
                                Open Settings
                            </button>
                            <button type="button" @click="activeTab = 'export'"
                                    class="text-[11px] font-sans font-bold uppercase tracking-wider text-rust hover:underline">
                                Export still available
                            </button>
                        </div>
                    </div>
                    <div x-show="publishMessage && publishStatus === 'success'"
                         class="border border-acid/40 bg-acid-wash px-4 py-3 text-sm font-serif text-acid-text"
                         x-text="publishMessage"></div>

                    <div class="pen-card bg-forge-black border-border-chassis p-6 overflow-hidden">
                        <div class="flex items-center justify-between mb-4 border-b border-border-chassis pb-4">
                            <div class="flex items-center space-x-2">
                                <div class="flex space-x-1.5">
                                    <div class="w-3 h-3 rounded-full bg-danger/80"></div>
                                    <div class="w-3 h-3 rounded-full bg-warning/80"></div>
                                    <div class="w-3 h-3 rounded-full bg-acid/80"></div>
                                </div>
                                <span class="text-steel-bright text-[10px] font-sans ml-4 uppercase tracking-widest font-bold">Publish log</span>
                            </div>
                            <div class="flex items-center space-x-2">
                                <span class="text-[10px] font-sans uppercase tracking-wider font-bold"
                                      :class="publishStatus === 'success'
                                        ? 'text-acid'
                                        : (publishStatus === 'error' ? 'text-danger' : 'text-steel-bright')"
                                      x-text="publishPhaseLabel"></span>
                            </div>
                        </div>
                        <pre x-ref="publishLogPre"
                             class="font-serif text-[13px] text-steel-bright leading-relaxed overflow-auto max-h-[500px] whitespace-pre-wrap scrollbar-thin scrollbar-thumb-steel-muted scrollbar-track-transparent pr-4"
                             x-text="publishLog.length ? publishLog.join('\n') : (publishing ? 'Starting publish…' : '')"></pre>
                    </div>
                </div>

                <!-- Empty / unconnected first-run -->
                <div x-show="!configured" x-cloak class="pen-card p-8 bg-card border-dashed">
                    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                        <div class="min-w-0 flex-1">
                            <p class="text-[10px] font-sans font-bold uppercase tracking-widest text-forge-mid mb-2">Deploy target</p>
                            <h2 class="text-2xl font-sans font-black uppercase tracking-tight text-forge-mid mb-3">
                                No host connected
                            </h2>
                            <p class="text-sm font-serif text-forge-dark max-w-lg leading-relaxed">
                                Add an SFTP host in Settings to deploy this site’s built <span class="font-mono text-xs font-bold">dist/</span>.
                                Until then, use the Export tab for a local static build — no host required.
                            </p>
                            <div class="mt-4 flex flex-wrap items-center gap-3">
                                <span class="inline-flex items-center gap-1.5 px-2 py-1 border border-border bg-canvas text-forge-mid text-[10px] font-sans font-bold uppercase tracking-wider">
                                    <span class="w-1.5 h-1.5 rounded-full bg-forge-mid/50"></span>
                                    Unconnected
                                </span>
                                <span class="text-xs font-serif text-forge-mid">Last published: never</span>
                            </div>
                        </div>
                        <div class="flex-shrink-0 flex flex-col items-stretch gap-2">
                            <button type="button" @click="activeTab = 'settings'"
                                    class="pen-btn-primary text-base px-8 py-3">
                                Connect a host
                            </button>
                            <button type="button" @click="activeTab = 'export'"
                                    class="pen-btn text-sm px-6 py-2">
                                Export instead
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab: Export -->
            <div x-show="activeTab === 'export'" class="space-y-6 max-w-6xl">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                <!-- Card 1: Export static site (streaming pipeline) -->
                <div class="pen-card p-8 bg-card">
                    <h3 class="text-lg font-bold uppercase tracking-tight text-primary mb-2 pb-2 border-b border-border/40">
                        Export static site
                    </h3>
                    <p class="text-sm font-serif text-forge-dark leading-relaxed mb-6">
                        Trigger the static generation pipeline including OG images.
                        By default this builds the <span class="font-mono font-bold text-rust" x-text="siteId"></span>
                        Content site (header picker). <span x-show="$store.app.edition === 'pro'" x-cloak>Choose “All sites” to write each site under its own output folder.</span>
                    </p>

                    <form class="space-y-6" @submit.prevent="startExportBuild()">
                        <div>
                            <label class="pen-label">Build scope</label>
                            <div class="flex flex-col gap-2 mt-1">
                                <label class="flex items-start gap-2 text-sm font-serif text-forge-dark cursor-pointer">
                                    <input type="radio" name="buildScope" value="active" x-model="exportBuildScope"
                                           class="mt-1 border-border text-rust focus:ring-rust"
                                           :disabled="exportBuilding">
                                    <span>
                                        Active Content site
                                        (<span class="font-mono font-bold text-rust" x-text="siteId"></span>)
                                    </span>
                                </label>
                                <label class="flex items-start gap-2 text-sm font-serif text-forge-dark cursor-pointer"
                                       x-show="$store.app.edition === 'pro'" x-cloak>
                                    <input type="radio" name="buildScope" value="all" x-model="exportBuildScope"
                                           class="mt-1 border-border text-rust focus:ring-rust"
                                           :disabled="exportBuilding">
                                    <span>All sites (output per site id)</span>
                                </label>
                            </div>
                        </div>

                        <div>
                            <label for="export-domain" class="pen-label">Target Domain</label>
                            <input type="text" x-model="exportBuildDomain" id="export-domain"
                                   placeholder="e.g., pencms.com"
                                   class="pen-input w-full"
                                   :disabled="exportBuilding">
                            <p class="text-[10px] text-forge-mid mt-1.5">
                                Optional override. Leave blank to use each site’s registry domain, then localhost.
                            </p>
                        </div>

                        <div class="flex justify-start">
                            <button type="submit"
                                    :disabled="!canHostPublish || exportBuilding || exporting || publishing"
                                    class="pen-btn-secondary flex items-center gap-2">
                                <template x-if="!exportBuilding">
                                    <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none">
                                        <path d="M180,104h20a8,8,0,0,1,8,8v96a8,8,0,0,1-8,8H56a8,8,0,0,1-8-8V112a8,8,0,0,1,8-8H76"
                                              stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                                        <polyline points="88 64 128 24 168 64" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" fill="none" />
                                        <line x1="128" y1="24" x2="128" y2="136" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                                    </svg>
                                </template>
                                <template x-if="exportBuilding">
                                    <svg class="w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                </template>
                                <span x-text="exportBuilding ? 'Building Pipeline…' : 'Export static site'"></span>
                            </button>
                        </div>
                    </form>
                </div>

                <!-- Card 2: Download as .zip -->
                <div class="pen-card p-8 bg-card">
                    <h3 class="text-lg font-bold uppercase tracking-tight text-primary mb-2 pb-2 border-b border-border/40">
                        Download as .zip
                    </h3>
                    <p class="text-sm font-serif text-forge-dark leading-relaxed mb-5">
                        Build the active Content site and download a full static tree as a
                        <span class="font-mono text-xs font-bold">.zip</span>
                        (saved to your browser Downloads folder). No host upload.
                    </p>

                    <div class="flex flex-wrap items-center gap-3 mb-4">
                        <button type="button"
                                class="pen-btn-secondary flex items-center gap-2"
                                @click="downloadExportZip()"
                                :disabled="!canHostPublish || exporting || exportBuilding || publishing">
                            <template x-if="!exporting">
                                <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none">
                                    <path d="M224,152v56a16,16,0,0,1-16,16H48a16,16,0,0,1-16-16V152"
                                          stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                                    <polyline points="88 120 128 160 168 120" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" fill="none" />
                                    <line x1="128" y1="40" x2="128" y2="160" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                                </svg>
                            </template>
                            <template x-if="exporting">
                                <svg class="w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                            </template>
                            <span x-text="exporting ? 'Building zip…' : 'Download as .zip'"></span>
                        </button>
                        <p class="text-[11px] font-serif text-forge-mid">
                            Site
                            <span class="font-mono text-[10px] font-bold text-rust" x-text="siteId"></span>
                            · download starts when the build finishes
                        </p>
                    </div>

                    <template x-if="exportStatus === 'success'">
                        <p class="text-xs font-serif text-acid mb-4" x-text="exportMessage"></p>
                    </template>
                    <template x-if="exportStatus === 'error'">
                        <p class="text-xs font-serif text-rust mb-4" x-text="exportError"></p>
                    </template>
                </div>
                </div>

                <!-- Build Execution Log -->
                <div x-show="exportBuildStarted" x-cloak
                     class="pen-card bg-forge-black border-border-chassis p-6 overflow-hidden">
                    <div class="flex items-center justify-between mb-4 border-b border-border-chassis pb-4">
                        <div class="flex items-center space-x-2">
                            <div class="flex space-x-1.5">
                                <div class="w-3 h-3 rounded-full bg-danger/80"></div>
                                <div class="w-3 h-3 rounded-full bg-warning/80"></div>
                                <div class="w-3 h-3 rounded-full bg-acid/80"></div>
                            </div>
                            <span class="text-steel-bright text-[10px] font-sans ml-4 uppercase tracking-widest font-bold">Build Execution Log</span>
                        </div>
                        <div class="flex items-center space-x-2"
                             :class="exportBuildStatus === 'active' ? 'animate-pulse' : ''">
                            <template x-if="exportBuildStatus === 'active'">
                                <div class="flex items-center space-x-2">
                                    <div class="w-2 h-2 rounded-full bg-acid"></div>
                                    <span class="text-acid text-[10px] font-bold uppercase tracking-widest">Active</span>
                                </div>
                            </template>
                            <template x-if="exportBuildStatus === 'complete'">
                                <span class="text-acid text-[10px] font-bold uppercase tracking-widest">Complete</span>
                            </template>
                            <template x-if="exportBuildStatus === 'failed'">
                                <span class="text-danger text-[10px] font-bold uppercase tracking-widest"
                                      x-text="'Failed (Code ' + exportBuildExitCode + ')'"></span>
                            </template>
                            <template x-if="exportBuildStatus === 'error'">
                                <span class="text-danger text-[10px] font-bold uppercase tracking-widest">Error</span>
                            </template>
                        </div>
                    </div>
                    <pre x-ref="exportBuildLogPre"
                         class="font-serif text-[13px] text-steel-bright leading-relaxed overflow-auto max-h-[500px] whitespace-pre-wrap scrollbar-thin scrollbar-thumb-steel-muted scrollbar-track-transparent pr-4"></pre>
                </div>
            </div>

            <!-- Tab: Settings -->
            <div x-show="activeTab === 'settings' && !loading" class="space-y-8 max-w-6xl">
                <div class="grid grid-cols-1 lg:grid-cols-10 gap-6 items-start">
                <div class="pen-card p-8 bg-card lg:col-span-7">
                    <h3 class="text-xl font-bold uppercase tracking-tight text-primary mb-4 pb-2 border-b border-border/40">
                        Host &amp; path
                    </h3>
                    <p class="text-xs font-serif text-forge-dark mb-6 leading-relaxed">
                        One publish target per site. Connection fields are stored on the server;
                        host secrets stay in your Zero-Knowledge vault (or a Deploy Grant for agents).
                    </p>

                    <div class="space-y-5">
                        <div>
                            <label class="pen-label block mb-1.5" for="publish-provider">Provider</label>
                            <select id="publish-provider"
                                    class="pen-input w-full text-sm"
                                    x-model="provider"
                                    @change="onProviderChange()">
                                <template x-for="p in providerOptions" :key="p.id">
                                    <option :value="p.id"
                                            :disabled="!p.enabled"
                                            x-text="p.enabled ? p.label : (p.label + ' — Coming soon')"></option>
                                </template>
                            </select>
                            
                        </div>

                        <!-- SFTP connection fields -->
                        <div x-show="isSftp" class="space-y-5" x-cloak>
                        <div class="grid grid-cols-3 gap-4">
                            <div class="col-span-2">
                                <label class="pen-label block mb-1.5" for="publish-host">Host</label>
                                <input type="text" id="publish-host" x-model="host"
                                       class="pen-input w-full text-sm"
                                       placeholder="example.com" autocomplete="off">
                            </div>
                            <div>
                                <label class="pen-label block mb-1.5" for="publish-port">Port</label>
                                <input type="number" id="publish-port" x-model="port"
                                       class="pen-input w-full text-sm"
                                       placeholder="22" min="1" max="65535">
                            </div>
                        </div>

                        <div>
                            <label class="pen-label block mb-1.5" for="publish-username">SFTP user</label>
                            <input type="text" id="publish-username" x-model="username"
                                   class="pen-input w-full text-sm"
                                   placeholder="deploy" autocomplete="off">
                        </div>

                        <div>
                            <label class="pen-label block mb-1.5" for="publish-remote-path">Remote path</label>
                            <input type="text" id="publish-remote-path" x-model="remote_path"
                                   class="pen-input w-full font-mono text-sm"
                                   placeholder="/var/www/html" autocomplete="off">
                        </div>
                        </div>

                        <!-- Catalog-driven fields (Pro adapters; Core SFTP/GitHub stay hardcoded) -->
                        <div x-show="!isSftp && !isGithubPages" class="space-y-5" x-cloak>
                            <template x-for="field in schemaFields" :key="field.name">
                                <div>
                                    <label class="pen-label block mb-1.5"
                                           :for="'publish-field-' + field.name"
                                           x-text="field.label"></label>
                                    <input type="text"
                                           :id="'publish-field-' + field.name"
                                           x-model="schemaValues[field.name]"
                                           class="pen-input w-full font-mono text-sm"
                                           :placeholder="field.placeholder || ''"
                                           autocomplete="off">
                                    <p class="text-[10px] text-forge-mid mt-1.5"
                                       x-show="field.help"
                                       x-text="field.help"></p>
                                </div>
                            </template>
                        </div>

                        <!-- GitHub Pages fields -->
                        <div x-show="isGithubPages" class="space-y-5" x-cloak>
                        <div>
                            <label class="pen-label block mb-1.5" for="publish-github-owner">Owner</label>
                            <input type="text" id="publish-github-owner" x-model="github_owner"
                                   class="pen-input w-full font-mono text-sm"
                                   placeholder="octocat" autocomplete="off">
                            <p class="text-[10px] text-forge-mid mt-1.5">
                                GitHub user or organization that owns the repository.
                            </p>
                        </div>
                        <div>
                            <label class="pen-label block mb-1.5" for="publish-github-repo">Repository</label>
                            <input type="text" id="publish-github-repo" x-model="github_repo"
                                   class="pen-input w-full font-mono text-sm"
                                   placeholder="my-site" autocomplete="off">
                            <p class="text-[10px] text-forge-mid mt-1.5">
                                Repository name only (not owner/repo). Pages source should be the branch below.
                            </p>
                        </div>
                        <div>
                            <label class="pen-label block mb-1.5" for="publish-github-branch">Pages branch</label>
                            <input type="text" id="publish-github-branch" x-model="github_pages_branch"
                                   class="pen-input w-full font-mono text-sm"
                                   placeholder="gh-pages" autocomplete="off">
                            <p class="text-[10px] text-forge-mid mt-1.5">
                                Branch PenCMS force-pushes (default <span class="font-mono">gh-pages</span>). Configure GitHub Pages to serve from this branch at <span class="font-mono">/</span>.
                            </p>
                        </div>
                        <div>
                            <label class="pen-label block mb-1.5" for="publish-github-cname">Custom domain (optional)</label>
                            <input type="text" id="publish-github-cname" x-model="github_pages_cname"
                                   class="pen-input w-full font-mono text-sm"
                                   placeholder="www.example.com" autocomplete="off">
                            <p class="text-[10px] text-forge-mid mt-1.5">
                                Written as a <span class="font-mono">CNAME</span> file on publish; used for the stored public URL when set.
                            </p>
                        </div>
                        </div>

                        <div>
                            <label class="pen-label mb-1.5 flex items-center gap-1.5" for="publish-public-url">
                                <span>Public URL</span>
                                <span class="relative inline-flex group/tip">
                                    <button type="button"
                                            class="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-forge-mid/60 text-[9px] font-sans font-black text-forge-mid hover:border-rust hover:text-rust focus:outline-none focus:border-rust focus:text-rust"
                                            aria-label="About Public URL">i</button>
                                    <span role="tooltip"
                                          class="pointer-events-none invisible opacity-0 group-hover/tip:visible group-hover/tip:opacity-100 group-focus-within/tip:visible group-focus-within/tip:opacity-100 transition-opacity absolute z-20 left-0 top-full mt-1.5 w-64 p-2.5 bg-[#111008] text-steel-bright text-[10px] font-serif font-normal leading-relaxed normal-case tracking-normal shadow-lg border border-border">
                                        Shown on the Publish tab as the live link.
                                        <span x-text="publicUrlHelp"></span>
                                    </span>
                                </span>
                            </label>
                            <input type="url" id="publish-public-url" x-model="public_url"
                                   class="pen-input w-full text-sm"
                                   :placeholder="publicUrlPlaceholder"
                                   autocomplete="off">
                            <p class="text-[10px] text-forge-mid mt-1.5" x-text="publicUrlHint"></p>
                        </div>

                        <!-- Webhooks Accordion Drawer -->
                        <div class="border border-border bg-canvas/40">
                            <button type="button"
                                    class="w-full flex items-center justify-between gap-3 px-3 py-2.5 select-none"
                                    @click="showWebhooks = !showWebhooks"
                                    :aria-expanded="showWebhooks">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">Webhooks</span>
                                <svg class="w-3.5 h-3.5 text-forge-mid transition-transform duration-200"
                                     :class="showWebhooks ? '' : '-rotate-90'"
                                     fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"
                                     aria-hidden="true">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                                </svg>
                            </button>
                            <div x-show="showWebhooks"
                                 x-cloak
                                 x-transition
                                 class="px-3 pb-3 pt-1 border-t border-border space-y-4">
                                <p class="text-[10px] text-forge-mid font-serif leading-relaxed">
                                    Post-publish notifications and HMAC signing. Most sites can leave these alone.
                                </p>
                                <div class="space-y-4">
                                    <div>
                                        <label class="pen-label mb-1.5 flex items-center gap-1.5" for="publish-webhook-url">
                                            Webhook URL
                                            <span class="relative inline-flex group/tip">
                                                <button type="button"
                                                        class="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-forge-mid/60 text-[9px] font-sans font-black text-forge-mid hover:border-rust hover:text-rust focus:outline-none focus:border-rust focus:text-rust"
                                                        aria-label="About post-publish webhooks">i</button>
                                                <span role="tooltip"
                                                      class="pointer-events-none invisible opacity-0 group-hover/tip:visible group-hover/tip:opacity-100 group-focus-within/tip:visible group-focus-within/tip:opacity-100 transition-opacity absolute z-20 left-0 top-full mt-1.5 w-64 p-2.5 bg-[#111008] text-steel-bright text-[10px] font-serif font-normal leading-relaxed normal-case tracking-normal shadow-lg border border-border">
                                                    After publish succeeds or fails, PenCMS POSTs a small JSON payload to this URL.
                                                    Optional signing secret adds an X-PenCMS-Signature header. Leave blank to disable.
                                                </span>
                                            </span>
                                        </label>
                                        <input type="url" id="publish-webhook-url" x-model="webhook_url"
                                               class="pen-input w-full text-sm"
                                               placeholder="https://example.com/hooks/publish"
                                               autocomplete="off">
                                        <p class="text-[10px] text-forge-mid mt-1.5">
                                            Optional. Fired after a successful or failed deploy finalize.
                                        </p>
                                    </div>

                                    <div>
                                        <label class="pen-label mb-1.5 flex items-center gap-1.5" for="publish-webhook-secret">
                                            Webhook signing secret
                                            <span class="relative inline-flex group/tip">
                                                <button type="button"
                                                        class="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-forge-mid/60 text-[9px] font-sans font-black text-forge-mid hover:border-rust hover:text-rust focus:outline-none focus:border-rust focus:text-rust"
                                                        aria-label="About webhook HMAC signing">i</button>
                                                <span role="tooltip"
                                                      class="pointer-events-none invisible opacity-0 group-hover/tip:visible group-hover/tip:opacity-100 group-focus-within/tip:visible group-focus-within/tip:opacity-100 transition-opacity absolute z-20 left-0 top-full mt-1.5 w-64 p-2.5 bg-[#111008] text-steel-bright text-[10px] font-serif font-normal leading-relaxed normal-case tracking-normal shadow-lg border border-border">
                                                    When set, requests include X-PenCMS-Signature: sha256=&lt;hex&gt; over the exact JSON body.
                                                    Leave blank to keep the saved secret; use Clear to remove it.
                                                </span>
                                            </span>
                                        </label>
                                        <input type="text" id="publish-webhook-secret" x-model="webhook_secret"
                                               class="pen-input w-full text-sm font-mono"
                                               :placeholder="has_webhook_secret && !_clearWebhookSecret
                                                 ? '••••••••  (saved — enter a new value to replace)'
                                                 : 'Optional shared secret'"
                                               autocomplete="off"
                                               @input="_clearWebhookSecret = false">
                                        <div class="flex items-center justify-between gap-2 mt-1.5">
                                            <p class="text-[10px] text-forge-mid">
                                                <span x-show="has_webhook_secret && !_clearWebhookSecret">Secret saved.</span>
                                                <span x-show="_clearWebhookSecret" class="text-rust">Will clear on save.</span>
                                                <span x-show="!has_webhook_secret && !_clearWebhookSecret">Optional. HMAC signing when set.</span>
                                            </p>
                                            <button type="button"
                                                    class="text-[10px] font-sans font-black uppercase tracking-wider text-forge-mid hover:text-rust focus:outline-none focus:text-rust"
                                                    x-show="has_webhook_secret && !_clearWebhookSecret"
                                                    @click="_clearWebhookSecret = true; webhook_secret = ''">
                                                Clear
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- SFTP auth method -->
                        <div x-show="isSftp" class="pt-4 border-t border-border/60" x-cloak>
                            <label class="pen-label mb-2 block">Authentication method</label>
                            <div class="flex gap-4">
                                <button type="button" @click="setAuthMethod('password')"
                                        class="flex-1 p-3 border-2 text-left transition-all"
                                        :class="auth_method === 'password' ? 'border-rust bg-rust-wash' : 'border-border bg-card hover:border-forge-mid'">
                                    <div class="font-sans font-black text-xs uppercase tracking-wider text-forge-dark">Password</div>
                                    <div class="text-[10px] text-forge-mid font-serif mt-0.5">Stored in your ZK vault</div>
                                </button>
                                <button type="button" @click="setAuthMethod('key')"
                                        class="flex-1 p-3 border-2 text-left transition-all"
                                        :class="auth_method === 'key' ? 'border-rust bg-rust-wash' : 'border-border bg-card hover:border-forge-mid'">
                                    <div class="font-sans font-black text-xs uppercase tracking-wider text-forge-dark">SSH Key</div>
                                    <div class="text-[10px] text-forge-mid font-serif mt-0.5">Install Ed25519 key</div>
                                </button>
                            </div>
                        </div>

                        <div x-show="usesPasswordAuth" class="space-y-4 pt-2" x-cloak>
                            <div>
                                <label class="pen-label mb-1.5 flex items-center gap-1.5" for="publish-password">
                                    <span x-text="tokenSecretLabel"></span>
                                    <span x-show="secretHelp" class="relative inline-flex group/tip" x-cloak>
                                        <button type="button"
                                                class="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-forge-mid/60 text-[9px] font-sans font-black text-forge-mid hover:border-rust hover:text-rust focus:outline-none focus:border-rust focus:text-rust"
                                                :aria-label="'About ' + tokenSecretLabel">i</button>
                                        <span role="tooltip"
                                              class="pointer-events-none invisible opacity-0 group-hover/tip:visible group-hover/tip:opacity-100 group-focus-within/tip:visible group-focus-within/tip:opacity-100 transition-opacity absolute z-20 left-0 top-full mt-1.5 w-64 p-2.5 bg-[#111008] text-steel-bright text-[10px] font-serif font-normal leading-relaxed normal-case tracking-normal shadow-lg border border-border"
                                              x-text="secretHelp"></span>
                                    </span>
                                </label>
                                <input id="publish-password"
                                       type="text"
                                       x-model="password"
                                       :placeholder="hasPassword ? '••••••••' : secretPlaceholder"
                                       class="pen-input w-full text-sm font-mono"
                                       autocomplete="off">
                                <span x-show="hasPassword" class="text-[10px] text-forge-mid mt-1 block"
                                      x-text="isTokenHost
                                        ? 'Saved API token is not shown. Enter a new one to update.'
                                        : 'Saved password is not shown. Enter a new one to update.'"></span>
                                <p x-show="secretCreateUrl && !hasPassword && !(password || '').trim()"
                                   class="text-[10px] text-forge-mid mt-1.5" x-cloak>
                                    <a :href="secretCreateUrl" target="_blank" rel="noopener noreferrer"
                                       class="text-rust underline hover:no-underline"
                                       x-text="secretCreateLabel"></a>
                                    <span class="text-forge-mid" x-show="secretCreateHint"
                                          x-text="' — ' + secretCreateHint"></span>
                                </p>
                            </div>
                            <div class="p-4 bg-rust-wash border border-rust/40">
                                <p class="text-[11px] text-forge-dark leading-relaxed font-serif">
                                    <strong>Zero-Knowledge Encryption:</strong>
                                    Secrets are encrypted locally in your browser using your Master Password.
                                    They are never written to <span class="font-mono text-[10px]">sites.yaml</span> or returned by the API.
                                    <span x-show="secretCreateUrl">
                                        Create a secret at
                                        <a :href="secretCreateUrl" target="_blank" rel="noopener noreferrer"
                                           class="text-rust underline hover:no-underline font-mono text-[10px]"
                                           x-text="secretCreateHost"></a>.
                                    </span>
                                </p>
                            </div>
                        </div>

                        <div x-show="isSftp && auth_method === 'key'" class="space-y-4 pt-2" x-cloak>
                            <div class="flex items-center gap-3">
                                <span class="font-sans font-black uppercase text-[10px] tracking-wider text-forge-dark">Install SSH key</span>
                                <template x-if="sshKeyExists">
                                    <span class="pen-badge bg-acid-wash text-acid-text border-acid-deep border">Key found</span>
                                </template>
                                <template x-if="!sshKeyExists && !sshKeyLoading">
                                    <span class="pen-badge bg-danger-bg text-danger border-danger border">No key</span>
                                </template>
                            </div>

                            <div x-show="sshKeyExists" class="space-y-3">
                                <label class="pen-label block">Public key</label>
                                <code class="block bg-[#111008] text-steel-bright border-l-4 border-rust p-4 font-mono text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap break-all" x-text="(sshPublicKey || '').trim()"></code>
                                <div class="flex flex-wrap gap-2">
                                    <button type="button" @click="copyPublicKey()" class="pen-btn-secondary pen-btn-sm" :disabled="copiedKey || !sshPublicKey">
                                        <span x-text="copiedKey ? 'Copied!' : 'Copy'"></span>
                                    </button>
                                </div>
                                <div class="p-4 bg-rust-wash border border-rust/40 space-y-2 font-serif text-xs leading-relaxed text-forge-dark">
                                    <h5 class="font-sans font-black uppercase text-[10px] tracking-wider text-rust">Authorize on the publish host</h5>
                                    <p>
                                        Add this public key to the host’s
                                        <code class="bg-card px-1 py-0.5 border border-border font-mono text-[10px]">~/.ssh/authorized_keys</code>
                                        for the deploy user. Same install key as
                                        <a href="admin-settings-storage.php" class="text-rust underline hover:no-underline">Storage → SSH Key Management</a>.
                                    </p>
                                </div>
                            </div>

                            <div x-show="!sshKeyExists && !sshKeyLoading" class="space-y-3">
                                <div class="p-4 bg-rust-wash border border-rust/40">
                                    <p class="font-serif text-xs leading-relaxed text-forge-dark">
                                        Generate the install Ed25519 key pair (shared with Content Storage SSH), then add the public key to the publish host.
                                    </p>
                                </div>
                                <button type="button" @click="generateSSHKey()" class="pen-btn-primary pen-btn-sm flex items-center gap-2" :disabled="!canHostPublish || generatingKey">
                                    <span x-text="generatingKey ? 'Generating…' : 'Generate Ed25519 Key Pair'"></span>
                                </button>
                                <p x-show="sshKeyError" class="text-xs text-danger font-mono" x-text="sshKeyError"></p>
                            </div>
                        </div>

                        <div class="flex flex-wrap items-center gap-4 pt-4 border-t border-border/60">
                            <button type="button" @click="save()" class="pen-btn-primary" :disabled="!canHostPublish || saving">
                                <span x-text="saving ? 'Saving…' : 'Save'"></span>
                            </button>
                            <button type="button" @click="testConnection()" class="pen-btn-secondary"
                                    :disabled="!canHostPublish || testing || testStatus === 'testing'">
                                <span x-text="testing || testStatus === 'testing' ? 'Testing…' : 'Test Connection'"></span>
                            </button>
                            <div class="text-xs font-mono font-bold flex items-center gap-1.5 min-w-0">
                                <span x-show="saveStatus === 'success'" class="text-acid-deep" x-text="saveMessage"></span>
                                <span x-show="saveStatus === 'error'" class="text-danger" x-text="saveMessage"></span>
                                <span x-show="testStatus === 'success'" class="text-acid-deep" x-text="testMessage"></span>
                                <span x-show="testStatus === 'error'" class="text-danger break-all" x-text="testMessage"></span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Deploy Grant (agentic publish) -->
                <div class="pen-card p-8 bg-card lg:col-span-3 flex flex-col gap-4" x-show="configured" x-cloak>
                    <div class="flex items-start justify-between gap-3 flex-wrap pb-2 border-b border-border/40">
                        <h3 class="text-lg font-bold uppercase tracking-tight text-primary"
                            x-text="deployGrantHeading"></h3>
                        <template x-if="grantEnrolled">
                            <span class="pen-badge bg-acid-wash text-acid-text border-acid-deep border shrink-0">Enrolled</span>
                        </template>
                        <template x-if="!grantEnrolled">
                            <span class="pen-badge bg-steel-wash text-forge-mid border-border border shrink-0">Off</span>
                        </template>
                    </div>
                    <p class="text-[11px] text-forge-mid font-serif leading-relaxed">
                        Enrolls a Deploy Grant so agent keys with scope
                        <code class="font-mono text-[10px]">publish</code>
                        can deploy without unlocking your vault.
                        Mint keys under
                        <a href="admin-settings-ai.php" class="text-rust underline hover:no-underline">Settings → AI</a>
                        (Read + Write + Publish).
                    </p>

                    <div class="p-4 bg-rust-wash border border-rust/40 space-y-2 font-serif text-xs leading-relaxed text-forge-dark">
                        <p x-show="auth_method === 'password'">
                            <strong>Leaves Zero-Knowledge for this secret:</strong>
                            Enrollment copies the SFTP password into server-side storage
                            decryptable by this install
                            (<span class="font-mono text-[10px]">data/publish-grants/</span>).
                            Agents never see the password — only PenCMS does at deploy time.
                        </p>
                        <p x-show="auth_method === 'token'">
                            <strong>Leaves Zero-Knowledge for this secret:</strong>
                            Enrollment copies the
                            <span x-text="tokenSecretLabel"></span>
                            into server-side storage
                            decryptable by this install
                            (<span class="font-mono text-[10px]">data/publish-grants/</span>).
                            Agents never see the token — only PenCMS does at deploy time.
                        </p>
                        <p x-show="auth_method === 'key'">
                            Key-auth grants are flag-only: agents use this install’s Ed25519 key
                            (no password duplicated into the grant store).
                        </p>
                        <p class="text-[10px] text-forge-mid">
                            Two revoke knobs: revoke the agent key (AI Settings) or revoke this grant — independently.
                        </p>
                    </div>

                    <div class="mt-auto flex flex-wrap items-center justify-end gap-3 pt-2">
                        <span class="text-xs font-mono font-bold mr-auto"
                              :class="grantMessageOk ? 'text-acid-deep' : 'text-danger'"
                              x-show="grantMessage" x-text="grantMessage"></span>
                        <button type="button" @click="enrollGrant()" class="pen-btn-primary pen-btn-sm"
                                :disabled="!canHostPublish || grantBusy || grantEnrolled"
                                x-show="!grantEnrolled">
                            <span x-text="grantBusy ? 'Enrolling…' : 'Enroll Deploy Grant'"></span>
                        </button>
                        <button type="button" @click="revokeGrant()" class="pen-btn-secondary pen-btn-sm"
                                :disabled="!canHostPublish || grantBusy || !grantEnrolled"
                                x-show="grantEnrolled">
                            <span x-text="grantBusy ? 'Revoking…' : 'Revoke Deploy Grant'"></span>
                        </button>
                    </div>
                </div>
                </div>
            </div>
        </main>
    </div>

    <?php include "includes/_admin-footer.php"; ?>
</body>
</html>
