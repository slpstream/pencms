<?php
$pageTitle = 'Setup First User';
include 'includes/_head.php';

// If we already have a user in cookies, redirect
if (isset($_COOKIE['pen_user_id']) && $_COOKIE['pen_user_id'] !== 'author') {
    header("Location: index.php");
    exit;
}
?>
<body class="bg-canvas flex items-center justify-center min-h-screen" x-data="setupForm">
    <div class="pen-panel p-8 w-full max-w-md space-y-6">
        <div class="text-center space-y-2">
            <h1 class="text-2xl font-sans font-black text-forge-black tracking-tight uppercase">PenCMS Setup</h1>
            <p class="text-sm text-forge-dark">Create the first administrator account</p>
        </div>

        <div x-show="error" x-cloak class="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-[2px]">
            <span x-text="error"></span>
        </div>

        <div x-show="success" x-cloak class="p-3 bg-green-50 border border-green-200 text-green-700 text-sm rounded-[2px]">
            User created successfully! Redirecting to login...
        </div>

        <div class="space-y-4" x-show="!success">
            <div>
                <label class="pen-label">Username</label>
                <input type="text" x-model="username" class="pen-input" placeholder="jdoe">
                <p class="text-[10px] text-steel-muted mt-1">A one-word ID for logging in.</p>
            </div>
            <div>
                <label class="pen-label">Master Password</label>
                <div class="relative">
                    <input :type="showPassword ? 'text' : 'password'" x-model="password" class="pen-input pr-10" placeholder="••••••••">
                    <button @click="showPassword = !showPassword" type="button" class="absolute inset-y-0 right-0 pr-3 flex items-center text-steel-muted hover:text-rust transition-colors focus:outline-none">
                        <!-- Eye-off (Obfuscate) - Shown when hidden -->
                        <svg x-show="!showPassword" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><line x1="48" y1="40" x2="208" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M154.91,157.6a40,40,0,0,1-53.82-59.2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M135.53,88.71a40,40,0,0,1,32.3,35.53" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M208.61,169.1C230.41,149.58,240,128,240,128S208,56,128,56a126,126,0,0,0-20.68,1.68" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M74,68.6C33.23,89.24,16,128,16,128s32,72,112,72a118.05,118.05,0,0,0,54-12.6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                        <!-- Eye (Reveal) - Shown when visible -->
                        <svg x-show="showPassword" x-cloak xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><path d="M128,56C48,56,16,128,16,128s32,72,112,72,112-72,112-72S208,56,128,56Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                    </button>
                </div>
                <p class="text-[10px] text-steel-muted mt-1">This will be used to encrypt your zero-knowledge keystore vault. Minimum 8 characters.</p>
            </div>
            <div>
                <label class="pen-label">Repeat Password</label>
                <div class="relative">
                    <input :type="showPasswordConfirm ? 'text' : 'password'" x-model="passwordConfirm" class="pen-input pr-10" placeholder="••••••••">
                    <button @click="showPasswordConfirm = !showPasswordConfirm" type="button" class="absolute inset-y-0 right-0 pr-3 flex items-center text-steel-muted hover:text-rust transition-colors focus:outline-none">
                        <!-- Eye-off (Obfuscate) - Shown when hidden -->
                        <svg x-show="!showPasswordConfirm" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><line x1="48" y1="40" x2="208" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M154.91,157.6a40,40,0,0,1-53.82-59.2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M135.53,88.71a40,40,0,0,1,32.3,35.53" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M208.61,169.1C230.41,149.58,240,128,240,128S208,56,128,56a126,126,0,0,0-20.68,1.68" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M74,68.6C33.23,89.24,16,128,16,128s32,72,112,72a118.05,118.05,0,0,0,54-12.6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                        <!-- Eye (Reveal) - Shown when visible -->
                        <svg x-show="showPasswordConfirm" x-cloak xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><path d="M128,56C48,56,16,128,16,128s32,72,112,72,112-72,112-72S208,56,128,56Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                    </button>
                </div>
            </div>
            
            <button @click="setupUser()" class="w-full pen-btn pen-btn-primary py-3 font-bold flex justify-center" :disabled="loading">
                <svg x-show="loading" class="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                <span x-text="loading ? 'Creating...' : 'Create Admin Account'"></span>
            </button>
        </div>
    </div>

    <script>
        document.addEventListener('alpine:init', () => {
            Alpine.data('setupForm', () => ({
                username: '',
                password: '',
                passwordConfirm: '',
                showPassword: false,
                showPasswordConfirm: false,
                loading: false,
                error: null,
                success: false,

                async setupUser() {
                    const cleanUsername = this.username.trim();
                    const cleanPassword = this.password.trim();

                    if (!cleanUsername || !cleanPassword || !this.passwordConfirm) {
                        this.error = 'Please fill in all fields.';
                        return;
                    }
                    if (cleanUsername.includes(' ')) {
                        this.error = 'Username must be a single word without spaces.';
                        return;
                    }
                    if (cleanPassword.length < 8) {
                        this.error = 'Password must be at least 8 characters long.';
                        return;
                    }
                    if (cleanPassword !== this.passwordConfirm.trim()) {
                        this.error = 'Passwords do not match.';
                        return;
                    }
                    this.loading = true;
                    this.error = null;
                    try {
                        const apiBase = window.AUTH.apiBase.replace('/v1', '');
                        const res = await fetch(`${apiBase}/auth/setup`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ 
                                username: cleanUsername, 
                                password: cleanPassword
                            })
                        });
                        const data = await res.json();
                        
                        if (res.ok) {
                            this.success = true;
                            setTimeout(() => {
                                window.location.href = 'login.php';
                            }, 1500);
                        } else {
                            this.error = data.detail || 'Setup failed';
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
