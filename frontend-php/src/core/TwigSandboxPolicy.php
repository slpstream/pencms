<?php

namespace Dossier;

use Twig\Sandbox\SecurityPolicy;

final class TwigSandboxPolicy
{
    public static function create(): SecurityPolicy
    {
        $tags = ['if', 'for', 'set', 'block', 'extends', 'include', 'macro', 'import', 'from'];
        // Notably NOT: sandbox, verbatim, do, flush, use

        $filters = [
            'default', 'raw', 'date', 'length', 'replace', 'title', 'trim', 'e', 'escape',
            'upper', 'lower', 'slice', 'first', 'last', 'join', 'split', 'sort', 'merge',
            'keys', 'json_encode', 'abs', 'number_format', 'format', 'url_encode', 'nl2br',
            'striptags', // used widely for decks/trumpets
        ];

        $functions = [
            'asset', 'contentAsset', 'publicAsset', 'contentUrl', 'archiveUrl',
            'partial', 'inlineCss', 'linkCss', 'menu',
            'date', 'max', 'min', 'range', 'random', 'attribute',
        ];

        $methods = [
            ThemeEngine::class => [
                'asset', 'contentAsset', 'publicAsset', 'partial', 'inlineCss', 'linkCss',
                'contentUrl', 'archiveUrl', 'isStatic', 'getLogoUrl', 'getAllDossiers',
            ],
        ];

        $properties = [];

        $tests = [
            'defined', 'empty', 'matches', 'odd', 'even', 'null', 'iterable',
            'same as', 'divisible by',
        ];

        $policy = new SecurityPolicy($tags, $filters, $methods, $properties, $functions, $tests);
        $policy->setStrict(true);
        return $policy;
    }
}
