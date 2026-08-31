<?php

declare(strict_types=1);

namespace Dossier;

final class UiStringsException extends \RuntimeException
{
}

/**
 * Resolve flat reader-facing UI strings for one site and render language.
 */
final class UiStrings
{
    public function __construct(
        private readonly string $engineDefaultsPath,
        private readonly string $themeDirectory,
        private readonly string $siteDirectory,
        private readonly string $defaultLanguage,
        private readonly bool $i18nActive,
    ) {
    }

    /**
     * Merge engine → theme → site default language → site target language.
     *
     * The inactive gate deliberately avoids reading optional theme/site files,
     * so staged or monolingual sites retain their legacy behavior.
     *
     * @return array<string, string>
     */
    public function resolve(string $targetLanguage): array
    {
        $resolved = $this->loadMap($this->engineDefaultsPath, true);
        if (!$this->i18nActive) {
            return $resolved;
        }

        $defaultLanguage = self::normalizeLanguage($this->defaultLanguage);
        $targetLanguage = self::normalizeLanguage($targetLanguage);
        if ($targetLanguage === '') {
            $targetLanguage = $defaultLanguage;
        }

        $layers = [
            $this->themeDirectory . '/strings.json',
            $this->siteDirectory . '/strings/' . $defaultLanguage . '.json',
        ];
        if ($targetLanguage !== $defaultLanguage) {
            $layers[] = $this->siteDirectory . '/strings/' . $targetLanguage . '.json';
        }

        foreach ($layers as $path) {
            $resolved = array_replace($resolved, $this->loadMap($path, false));
        }
        return $resolved;
    }

    /**
     * @return array<string, string>
     */
    private function loadMap(string $path, bool $required): array
    {
        if (!is_file($path)) {
            if ($required) {
                throw $this->invalid($path, 'file is missing');
            }
            return [];
        }

        $raw = file_get_contents($path);
        if ($raw === false) {
            throw $this->invalid($path, 'file could not be read');
        }

        try {
            $decoded = json_decode($raw, false, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            throw $this->invalid($path, 'invalid JSON: ' . $e->getMessage());
        }
        if (!$decoded instanceof \stdClass) {
            throw $this->invalid($path, 'top-level value must be a JSON object');
        }

        $strings = [];
        foreach (get_object_vars($decoded) as $key => $value) {
            if (
                preg_match('/^[A-Za-z][A-Za-z0-9_.-]*$/D', $key) !== 1
                || !is_string($value)
            ) {
                throw $this->invalid(
                    $path,
                    "key '{$key}' must use a flat string value and a valid identifier"
                );
            }
            $strings[$key] = $value;
        }
        return $strings;
    }

    private function invalid(string $path, string $reason): UiStringsException
    {
        return new UiStringsException(
            "{$path}: {$reason}. Fix: provide a flat JSON object of string keys and string values."
        );
    }

    private static function normalizeLanguage(string $language): string
    {
        return strtolower(str_replace('_', '-', trim($language)));
    }
}
