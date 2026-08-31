<?php
$pageTitle = 'Login';
include 'includes/_head.php';
?>
<body class="bg-canvas flex items-center justify-center min-h-screen" x-data="loginForm">
    <div class="pen-panel p-8 w-full max-w-md space-y-6">
        <div class="text-center space-y-2">
            <h1 class="text-2xl font-sans font-black text-forge-black tracking-tight uppercase">PenCMS</h1>
            <p class="text-sm text-forge-dark">Sign in to your account</p>
        </div>

        <div x-show="error" x-cloak class="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-[2px]">
            <span x-text="error"></span>
        </div>

        <div class="space-y-4">
            <div>
                <label class="pen-label">Username / UUID</label>
                <input type="text" x-model="username" class="pen-input" placeholder="jdoe" @keydown.enter="login">
            </div>
            <div>
                <label class="pen-label">Password</label>
                <div class="relative">
                    <input :type="showPassword ? 'text' : 'password'" x-model="password" class="pen-input pr-10" placeholder="••••••••" @keydown.enter="login">
                    <button @click="showPassword = !showPassword" type="button" class="absolute inset-y-0 right-0 pr-3 flex items-center text-steel-muted hover:text-rust transition-colors focus:outline-none">
                        <!-- Eye-off (Obfuscate) - Shown when hidden -->
                        <svg x-show="!showPassword" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><line x1="48" y1="40" x2="208" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M154.91,157.6a40,40,0,0,1-53.82-59.2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M135.53,88.71a40,40,0,0,1,32.3,35.53" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M208.61,169.1C230.41,149.58,240,128,240,128S208,56,128,56a126,126,0,0,0-20.68,1.68" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M74,68.6C33.23,89.24,16,128,16,128s32,72,112,72a118.05,118.05,0,0,0,54-12.6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                        <!-- Eye (Reveal) - Shown when visible -->
                        <svg x-show="showPassword" x-cloak xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><path d="M128,56C48,56,16,128,16,128s32,72,112,72,112-72,112-72S208,56,128,56Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                    </button>
                </div>
            </div>
            
            <button @click="login()" class="w-full pen-btn pen-btn-primary py-3 font-bold flex justify-center" :disabled="loading">
                <svg x-show="loading" class="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                <span x-text="loading ? 'Authenticating...' : 'Sign In'"></span>
            </button>
        </div>
    </div>

    <script>
        document.addEventListener('alpine:init', () => {
            Alpine.data('loginForm', () => ({
                username: '',
                password: '',
                showPassword: false,
                loading: false,
                error: null,

                async init() {
                    const params = new URLSearchParams(window.location.search);
                    if (params.get('error') === 'unauthorized') {
                        this.error = 'Please sign in to access the dashboard.';
                        window.history.replaceState({}, document.title, window.location.pathname);
                    }
                    try {
                        const apiBase = window.AUTH.apiBase.replace('/v1', '');
                        const res = await fetch(`${apiBase}/auth/status`);
                        const data = await res.json();
                        if (res.ok && data.initialized === false) {
                            window.location.href = 'setup.php';
                        }
                    } catch (e) {
                        console.warn("Could not check system status");
                    }
                },

                async login() {
                    const cleanUsername = this.username.trim();
                    const cleanPassword = this.password.trim();

                    if (!cleanUsername || !cleanPassword) {
                        this.error = 'Please fill in both fields.';
                        return;
                    }
                    this.loading = true;
                    this.error = null;
                    try {
                        const apiBase = window.AUTH.apiBase.replace('/v1', '');
                        const res = await fetch(`${apiBase}/auth/login`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ username: cleanUsername, password: cleanPassword })
                        });
                        const data = await res.json();
                        
                        if (res.ok) {
                            // On success, backend sets an HttpOnly cookie.
                            sessionStorage.setItem('pen_master_password', cleanPassword);
                            
                            // Set cookies for frontend auth check
                            document.cookie = `pen_user_id=${data.user.uuid}; path=/; max-age=604800`;
                            document.cookie = `pen_role=${data.user.role}; path=/; max-age=604800`;
                            
                            window.location.href = 'index.php';
                        } else if (res.status === 403 && data.detail === 'account_suspended') {
                            this.error = 'Your account is suspended.';
                        } else {
                            this.error = (typeof data.detail === 'string' && data.detail) ? data.detail : 'Login failed';
                        }
                    } catch (e) {
                        this.error = 'Network error. Could not reach API.';
                    } finally {
                        this.loading = false;
                    }
                }
            }));
        });
    </script>
</body>
</html>
