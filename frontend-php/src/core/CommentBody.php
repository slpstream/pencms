<?php

declare(strict_types=1);

namespace Dossier;

use League\CommonMark\Extension\CommonMark\Node\Inline\Image;
use League\CommonMark\Extension\CommonMark\Node\Inline\Link;
use League\CommonMark\GithubFlavoredMarkdownConverter;
use League\CommonMark\Node\Node;
use League\CommonMark\Renderer\ChildNodeRendererInterface;
use League\CommonMark\Renderer\NodeRendererInterface;
use League\CommonMark\Util\HtmlElement;
use League\CommonMark\Util\RegexHelper;
use League\Config\ConfigurationAwareInterface;
use League\Config\ConfigurationInterface;

/**
 * Safe GFM for public comment bodies. Never use PostRenderer's html_input=allow converter.
 */
final class CommentBody
{
    private static ?GithubFlavoredMarkdownConverter $converter = null;

    public static function toHtml(string $markdown): string
    {
        return trim((string) self::converter()->convert($markdown));
    }

    /**
     * @param list<mixed> $comments
     * @return list<array<string, mixed>>
     */
    public static function enrichComments(array $comments): array
    {
        $out = [];
        foreach ($comments as $comment) {
            if (!is_array($comment)) {
                continue;
            }
            $body = (string) ($comment['body'] ?? '');
            $comment['body_html'] = self::toHtml($body);
            $out[] = $comment;
        }

        return $out;
    }

    private static function converter(): GithubFlavoredMarkdownConverter
    {
        if (self::$converter instanceof GithubFlavoredMarkdownConverter) {
            return self::$converter;
        }

        $converter = new GithubFlavoredMarkdownConverter([
            'html_input' => 'escape',
            'allow_unsafe_links' => false,
        ]);
        $environment = $converter->getEnvironment();
        $environment->addRenderer(Image::class, new CommentImageRenderer(), 100);
        $environment->addRenderer(Link::class, new CommentLinkRenderer(), 100);
        self::$converter = $converter;

        return self::$converter;
    }
}

final class CommentImageRenderer implements NodeRendererInterface
{
    public function render(Node $node, ChildNodeRendererInterface $childRenderer): string
    {
        Image::assertInstanceOf($node);

        return $childRenderer->renderNodes($node->children());
    }
}

final class CommentLinkRenderer implements NodeRendererInterface, ConfigurationAwareInterface
{
    private ConfigurationInterface $config;

    public function render(Node $node, ChildNodeRendererInterface $childRenderer): HtmlElement
    {
        Link::assertInstanceOf($node);

        $attrs = $node->data->get('attributes');
        if (!is_array($attrs)) {
            $attrs = [];
        }
        $forbidUnsafeLinks = !$this->config->get('allow_unsafe_links');
        if (!($forbidUnsafeLinks && RegexHelper::isLinkPotentiallyUnsafe($node->getUrl()))) {
            $attrs['href'] = $node->getUrl();
        }
        if (($title = $node->getTitle()) !== null) {
            $attrs['title'] = $title;
        }
        $attrs['rel'] = 'nofollow noopener';
        $attrs['target'] = '_blank';

        return new HtmlElement('a', $attrs, $childRenderer->renderNodes($node->children()));
    }

    public function setConfiguration(ConfigurationInterface $configuration): void
    {
        $this->config = $configuration;
    }
}
