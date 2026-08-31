/**
 * PenCMS admin Tailwind theme (Stahl & Feuer).
 *
 * Source of truth for colors / fonts / tracking that used to live as
 * duplicated inline `tailwind.config = {…}` in _admin-head.php and _head.php.
 * Rebuilt into src/admin/css/admin.css by ./build-admin-css.sh
 * (Tailwind standalone CLI v3 — no Node, no Vite).
 *
 * Content globs use __dirname so the build is independent of cwd.
 */
const path = require('path');

const adminDir = path.join(__dirname, '../src/admin');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    path.join(adminDir, '**/*.php'),
    path.join(adminDir, '**/*.js'),
    path.join(adminDir, 'css/style.css'),
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: '#f5f3f0',
        card: '#ffffff',
        sidebar: '#1e1a17',
        nav: '#141210',
        'forge-black': '#0f0d0b',
        'forge-dark': '#2a2420',
        'forge-mid': '#6b5e55',
        'steel-bright': '#c8c0b8',
        'steel-muted': '#7a6e66',
        'steel-light': '#e8e2dc',
        rust: '#cc4a0a',
        'rust-deep': '#a83808',
        'rust-wash': '#fff0e8',
        'rust-bright': '#e8631a',
        acid: '#8fcc00',
        'acid-deep': '#6aaa00',
        'acid-wash': '#f0fad0',
        'acid-bright': '#a8e000',
        'acid-ink': '#0a1a00',
        'acid-text': '#3d5800',
        border: '#d8d0c8',
        'border-accent': '#f0c8a0',
        'border-weld': '#0f0d0b',
        'border-chassis': '#3a3028',
        'status-live': '#166534',
        'status-live-bg': '#dcfce7',
        'status-draft': '#1e1a17',
        danger: '#b91c1c',
        'danger-bg': '#fef2f2',
        warning: '#f59e0b',
        'warning-bg': '#fffbeb',
      },
      fontFamily: {
        sans: ['Mozilla Headline', 'system-ui', '-apple-system', 'sans-serif'],
        serif: ['Atkinson Hyperlegible Next', 'system-ui', '-apple-system', 'sans-serif'],
      },
      letterSpacing: {
        label: '0.14em',
        nav: '0.05em',
        btn: '0.06em',
      },
      lineHeight: {
        prose: '1.55',
        heading: '1.15',
        ui: '1.3',
      },
      borderRadius: {
        minimal: '2px',
      },
      boxShadow: {
        sm: '0 1px 3px 0 rgba(15,8,4,0.15)',
        md: '0 4px 8px -1px rgba(15,8,4,0.20), 0 2px 4px -1px rgba(15,8,4,0.12)',
        lg: '0 10px 20px -3px rgba(15,8,4,0.18), 0 4px 8px -2px rgba(15,8,4,0.10)',
        stamp: '3px 3px 0 rgba(0,0,0,0.30)',
      },
    },
  },
  plugins: [],
};
