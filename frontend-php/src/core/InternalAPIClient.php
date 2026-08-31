<?php
/**
 * Internal API Client for PenCMS Blog Frontend
 * 
 * Fetches content and configuration from the local Python API service.
 * This allows the PHP frontend to remain storage-agnostic.
 */

namespace Dossier;

class InternalAPIClient {
    private $baseUrl;
    private $timeout = 30;
    private string $siteId = 'default';

    public function __construct(?string $siteId = null) {
        $ini = parse_ini_file(__DIR__ . '/../../../backend-python/config.ini', true);
        
        // Resolve Port with graceful fallback
        $port = $ini['Server']['api_port'] ?? 8000;
        if (!is_numeric($port) || $port < 1 || $port > 65535) {
            $port = 8000;
        }

        $override = getenv('PENCMS_INTERNAL_API_URL');
        $this->baseUrl = $override !== false && trim($override) !== ''
            ? rtrim(trim($override), '/')
            : "http://localhost:{$port}/api";
        if ($siteId !== null && trim($siteId) !== '') {
            $this->siteId = strtolower(trim($siteId));
        }
    }

    public function setSiteId(string $siteId): void
    {
        $this->siteId = strtolower(trim($siteId)) ?: 'default';
    }

    public function getSiteId(): string
    {
        return $this->siteId;
    }

    /**
     * @return list<string>
     */
    private function buildHeaders(array $extra = []): array
    {
        $headers = $extra;
        $vaultContentPass = getenv('VAULT_CONTENT_PASS');
        $vaultAssetsPass = getenv('VAULT_ASSETS_PASS');
        if ($vaultContentPass !== false && $vaultContentPass !== '') {
            $headers[] = "X-Vault-Content-Pass: " . $vaultContentPass;
        }
        if ($vaultAssetsPass !== false && $vaultAssetsPass !== '') {
            $headers[] = "X-Vault-Assets-Pass: " . $vaultAssetsPass;
        }
        if ($this->siteId !== '') {
            $headers[] = "X-Pen-Site-Id: " . $this->siteId;
        }
        return $headers;
    }

    /**
     * Perform a GET request to the internal API.
     */
    public function get($endpoint, $params = []) {
        $url = $this->baseUrl . $endpoint;
        if (!empty($params)) {
            $url .= '?' . http_build_query($params);
        }

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, $this->timeout);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        
        $headers = $this->buildHeaders();
        if (!empty($headers)) {
            curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        }
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);

        if ($response === false) {
            throw new \Exception("Internal API Connection Failed: {$error} (URL: {$url})");
        }

        if ($httpCode >= 400) {
            $data = json_decode($response, true);
            $detail = $data['detail'] ?? 'Unknown Error';
            throw new \Exception("API Error [{$httpCode}]: {$detail}");
        }

        return json_decode($response, true);
    }

    /**
     * Perform a POST request to the internal API.
     */
    public function post($endpoint, $data = []) {
        $url = $this->baseUrl . $endpoint;

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, $this->timeout);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        
        $headers = $this->buildHeaders(['Content-Type: application/json']);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);

        if ($response === false) {
            throw new \Exception("Internal API Connection Failed: {$error} (URL: {$url})");
        }

        if ($httpCode >= 400) {
            $data = json_decode($response, true);
            $detail = $data['detail'] ?? 'Unknown Error';
            throw new \Exception("API Error [{$httpCode}]: {$detail}");
        }

        return json_decode($response, true);
    }

    /**
     * Check if a raw asset exists using a fast GET request.
     * Logical paths (e.g. images/content/...) are resolved under the active site.
     */
    public function assetExists($path) {
        $clean = ltrim((string) $path, '/');
        if ($clean === '') {
            return false;
        }
        if (str_starts_with($clean, 'api/assets/raw/')) {
            $clean = substr($clean, strlen('api/assets/raw/'));
        }
        if (!preg_match('#^sites/[^/]+/assets/#', $clean)) {
            $clean = 'sites/' . $this->siteId . '/assets/' . $clean;
        }
        $url = $this->baseUrl . '/assets/raw/' . $clean;
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_NOBODY, true);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'HEAD');
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, $this->timeout);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        
        $headers = $this->buildHeaders();
        if (!empty($headers)) {
            curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        }
        
        curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        return $httpCode === 200;
    }

    /**
     * Get the base URL for the API.
     */
    public function getBaseUrl() {
        return $this->baseUrl;
    }

    /**
     * Get the effective asset base URL from the API config.
     */
    public function getAssetBaseUrl() {
        try {
            $config = $this->get('/config');
            return $config['asset_base_url'] ?? '/assets/';
        } catch (\Exception $e) {
            return '/assets/';
        }
    }
}
