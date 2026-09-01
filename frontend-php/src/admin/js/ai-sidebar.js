/**
 * PenCMS AI Sidebar Controller (ai-sidebar.js)
 * Alpine.js component for the AI Assistant sidebar card.
 */

const DEBUG_AI = false; // Set this to true for development, toggle this to false before production

// ---------------------------------------------------------------------------
// Module-scope: configure two marked instances once at init.
//
//   innerMd — used for the inner content of blockquotes that we extract in
//             the preprocess hook below. Same configuration as `md`, but no
//             preprocess hook (so it never recurses into blockquote-detection).
//   md      — used for the chat message body.
//
// All renderer overrides below use v15+ object-destructured signatures and
// call `this.parser.parseInline(tokens)` for inline content. The renderer
// captures `role` via a closure over the module-scoped `_currentRole`, NOT via
// `md.use()` per render call — this avoids a streaming-time race where the
// last call's role could bleed into concurrent renders of other messages.
// ---------------------------------------------------------------------------

let _currentRole = "assistant";

const innerMd = new marked.Marked();
innerMd.use({
  renderer: {
    paragraph({ tokens }) {
      return "<p>" + this.parser.parseInline(tokens) + "</p>";
    },
    codespan({ text }) {
      return (
        '<code class="bg-[#fcfbf9] px-1.5 py-0.5 rounded font-mono text-xs border border-border/80">' +
        escapeHtml(text) +
        "</code>"
      );
    },
  },
});
innerMd.use({ gfm: true, breaks: true });

const md = new marked.Marked();

// Cache-bust media image URLs in the Markdown renderer so that when the LLM
// embeds an image via ![alt](url) in its text response, a regenerated image
// is never served from the browser cache under the same URL.
const _mediaUrlBusters = new Map();

md.use({
  hooks: {
    preprocess(src) {
      // Extract runs of consecutive `>` lines. Each run is rendered as a
      // Tailwind-styled <blockquote> whose body is the inner-Markdown
      // rendering of the stripped lines — so **bold**, `code`, lists, etc.
      // work inside a blockquote. The nested rendering does NOT recurse
      // into blockquotes itself (innerMd has no preprocess hook), matching
      // the existing behavior of the old regex implementation.
      const lines = src.split("\n");
      const out = [];
      let inBQ = false;
      let bqLines = [];
      const flush = () => {
        if (bqLines.length === 0) return;
        if (out.length && out[out.length - 1].trim() !== "") out.push("");
        const innerText = bqLines.join("\n");
        const innerHtml = innerMd.parse(innerText);
        out.push(
          '<blockquote class="border-l-2 border-rust/60 pl-3 my-2 italic leading-snug text-steel-muted">' +
            innerHtml +
            "</blockquote>",
        );
        out.push("");
        bqLines = [];
      };
      for (const line of lines) {
        const m = line.match(/^( {0,3})>+ ?(.*)$/);
        if (m) {
          if (!inBQ) {
            inBQ = true;
            bqLines = [];
          }
          bqLines.push(m[2]);
        } else {
          if (inBQ) {
            flush();
            inBQ = false;
          }
          out.push(line);
        }
      }
      if (inBQ) flush();
      return out.join("\n");
    },
    postprocess(html) {
      // XSS defense-in-depth. marked's defaults escape `&`/`<`/`>` inside
      // *text nodes* but pass through raw HTML blocks/attributes. This hook
      // strips dangerous tags, event handlers, and unsafe URI schemes in
      // href/src/xlink:href/formaction.
      //
      // TODO: consider adopting DOMPurify (~20 KB) for a full
      // browser-grade sanitizer if the threat model widens (e.g. if AI can
      // be coerced into unusual encoded payloads).
      return html
        .replace(/<script\b[\s\S]*?<\/script>/gi, "")
        .replace(/<iframe\b[\s\S]*?<\/iframe>/gi, "")
        .replace(/<style\b[\s\S]*?<\/style>/gi, "")
        .replace(/<object\b[\s\S]*?<\/object>/gi, "")
        .replace(/<embed\b[\s\S]*?<\/embed>/gi, "")
        .replace(/\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, "")
        .replace(
          /(\b(?:href|src|xlink:href|formaction)\s*=\s*)(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi,
          (_m, prefix, q1, q2, q3) => {
            const raw =
              q1 !== undefined ? q1 : q2 !== undefined ? q2 : q3 || "";
            // Decode named and numeric character references (e.g.
            // `&#x6A;avascript:` or `java&#x73;cript:`) before scheme
            // matching, so encoded payloads don't slip past the regex.
            // The browser will decode these entities at parse time and
            // execute the resulting `javascript:` URL.
            const decoded = raw.replace(
              /&(?:#x[0-9a-f]+|#[0-9]+|[a-z][a-z0-9]+);/gi,
              (ent) => {
                try {
                  const d = document.createElement("textarea");
                  d.innerHTML = ent;
                  return d.value;
                } catch (e) {
                  return ent;
                }
              },
            );
            if (
              /^(?:j[\s\x00-\x1f]*a[\s\x00-\x1f]*v[\s\x00-\x1f]*a[\s\x00-\x1f]*s[\s\x00-\x1f]*c[\s\x00-\x1f]*r[\s\x00-\x1f]*i[\s\x00-\x1f]*p[\s\x00-\x1f]*t[\s\x00-\x1f]*:|v[\s\x00-\x1f]*b[\s\x00-\x1f]*s[\s\x00-\x1f]*c[\s\x00-\x1f]*r[\s\x00-\x1f]*i[\s\x00-\x1f]*p[\s\x00-\x1f]*t[\s\x00-\x1f]*:|d[\s\x00-\x1f]*a[\s\x00-\x1f]*t[\s\x00-\x1f]*a[\s\x00-\x1f]*:)/i.test(
                decoded,
              )
            ) {
              return prefix + '"#"';
            }
            return _m;
          },
        );
    },
  },
  renderer: {
    paragraph({ tokens }) {
      const cls = _currentRole === "user" ? "leading-tight" : "leading-relaxed";
      return `<p class="mb-2 ${cls}">${this.parser.parseInline(tokens)}</p>`;
    },
    // No blockquote renderer override — blockquotes are emitted as raw HTML
    // blocks by the preprocess hook.
    codespan({ text }) {
      return (
        '<code class="bg-[#fcfbf9] px-1.5 py-0.5 rounded font-mono text-xs border border-border/80">' +
        escapeHtml(text) +
        "</code>"
      );
    },
    code({ text, lang }) {
      // Fenced code block. `text` is raw (marked v15+), so escape it.
      const langLabel =
        lang && /^[a-zA-Z0-9+#-]{1,16}$/.test(lang)
          ? `<span class="text-steel-muted block mb-1.5 select-none font-sans font-bold uppercase tracking-wider text-[10px]">${lang}</span>`
          : "";
      return (
        '<div class="relative group my-2">' +
        '<pre class="bg-[#fcfbf9] border border-border/80 p-3 rounded font-mono text-xs overflow-x-auto select-text">' +
        langLabel +
        '<code class="font-mono text-xs">' +
        escapeHtml(text) +
        "</code></pre>" +
        '<button class="copy-code-btn absolute top-2 right-2 p-1.5 rounded border border-border/80 bg-[#fcfbf9] hover:bg-[#f5f3f0] text-forge-mid hover:text-rust opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity duration-150 shadow-sm" title="Copy code to clipboard">' +
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4"><rect width="256" height="256" fill="none"/><polyline points="168 168 216 168 216 40 88 40 88 88" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><rect x="40" y="88" width="128" height="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>' +
        "</button>" +
        "</div>"
      );
    },
    heading({ tokens, depth }) {
      const tag = "h" + Math.min(depth, 4);
      const text = this.parser.parseInline(tokens);
      if (depth === 1)
        return `<${tag} class="text-xl font-bold mt-4 mb-2 leading-none text-forge-black">${text}</${tag}>`;
      if (depth === 2)
        return `<${tag} class="text-lg font-bold mt-4 mb-2 leading-tight text-forge-black">${text}</${tag}>`;
      if (depth === 3)
        return `<${tag} class="text-base font-bold mt-3 mb-1 leading-snug text-forge-black">${text}</${tag}>`;
      return `<${tag} class="text-sm font-bold mt-3 mb-1 leading-normal text-forge-black">${text}</${tag}>`;
    },
    // Intercept media images in LLM Markdown responses and apply a
    // per-URL cache-buster so the browser never serves a stale file.
    image({ href, title, tokens }) {
      const alt = tokens ? this.parser.parseInline(tokens) : "";
      // Strip any pre-existing query string then append our buster
      if (href && /\/api\/(assets\/raw|v1\/media\/files)\//.test(href)) {
        const buster = _mediaUrlBusters.get(href);
        if (buster) {
          href = href.split("?")[0] + "?t=" + buster;
        }
      }
      let attrs = `src="${escapeHtml(href)}" alt="${alt}"`;
      if (title) attrs += ` title="${escapeHtml(title)}"`;
      return `<img ${attrs} class="max-h-40 rounded border border-border my-1" style="display:block" />`;
    },
    // Lists: rely on existing CSS rules in admin-editor.php
    // for spacing/padding. The bullet/numbering markers come from the
    // `list-style-type` CSS rules we added in this PR. We deliberately do
    // NOT add Tailwind classes here, because the Tailwind reset sets
    // `list-style: none` on `ul`/`ol` which would visually break bullets
    // unless overridden in CSS.
  },
});
md.use({ gfm: true, breaks: true });

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

const TOOL_DEFINITIONS = [
  {
    type: "function",
    function: {
      name: "attach_image_to_post",
      description:
        "Write an attached image to the post's media gallery and return its public URL. Use this when the user asks you to include an attached image in the post (e.g. 'add this image to the post', 'include this in the media gallery'). This tool does NOT insert the image into the body text — you must separately call write_content_file to add the image shortcode to the body. The user must have attached images in the current turn for this tool to work.",
      parameters: {
        type: "object",
        properties: {
          image_index: {
            type: "number",
            description:
              "Zero-based index of the attached image to use. Use the index shown in the attached images list. If the user attaches a single image, use 0.",
          },
          filename: {
            type: "string",
            description:
              "The destination filename including directory (e.g. 'images/content/coastal-view.jpg'). Use the original filename if sensible, or create a descriptive one.",
          },
          caption: {
            type: "string",
            description: "Optional caption for the image.",
          },
          alt_text: {
            type: "string",
            description: "Optional alt text for accessibility.",
          },
        },
        required: ["image_index", "filename"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "get_site_config",
      description: "Read site settings, taxonomy, and collection schemas.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "list_collections",
      description: "List all available content collections.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "list_collection_entries",
      description:
        "List entries in a collection (paginated). Returns slug, title, status, modified_at.",
      parameters: {
        type: "object",
        properties: {
          collection_name: {
            type: "string",
            description: "The collection name (e.g. 'posts')",
          },
          page: { type: "integer", default: 1, description: "Page number" },
          limit: {
            type: "integer",
            default: 20,
            description: "Number of items per page",
          },
        },
        required: ["collection_name"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "read_page_metadata",
      description:
        "Return frontmatter + stats for a content entry, without the body. Includes an opaque `version` token (file mtime) for optional optimistic concurrency on a later write_content_file call.",
      parameters: {
        type: "object",
        properties: {
          slug: { type: "string", description: "The page identifier slug" },
        },
        required: ["slug"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "read_page_content",
      description:
        "Return the full Markdown body (and partials, if composite) of a page. Includes an opaque `version` token (file mtime) for optional optimistic concurrency on a later write_content_file call.",
      parameters: {
        type: "object",
        properties: {
          slug: { type: "string", description: "The page identifier slug" },
        },
        required: ["slug"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "search_content",
      description:
        "Full-text search across all content (title, frontmatter, body).",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search query" },
          limit: {
            type: "integer",
            default: 20,
            description: "Max results limit",
          },
        },
        required: ["query"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "list_media",
      description:
        "Browse the media library. Returns filenames and public URLs.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "create_post",
      description:
        "Create a new empty post as a stub. Provide a name (used to derive the URL slug) and optionally a category. After creation, use write_content_file with the returned slug to add body content.",
      parameters: {
        type: "object",
        properties: {
          name: {
            type: "string",
            description: "The post name (e.g. 'My Great Post'). Used to derive the URL slug.",
          },
          category: {
            type: "string",
            description: "Content category. Defaults to the site's primary category if omitted. Call get_site_config to see valid terms.",
          },
        },
        required: ["name"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "write_content_file",
      description:
        "Create or update the content file currently open in the editor. The slug MUST match the Currently Open Document slug shown above. Validates frontmatter against schema before writing. After a successful write, the editor surface is refreshed from disk so the user sees the change. Optionally pass `expected_version` from a prior read to participate in optimistic concurrency (mismatches return 409 version_conflict unless force is true). To schedule a future go-live, include status: \"published\" and publish_at (UTC ISO-8601 ending in Z) in frontmatter.",
      parameters: {
        type: "object",
        properties: {
          slug: {
            type: "string",
            description:
              "The page identifier slug. Must match the open document's Slug shown in the context, unless the user explicitly names a different page.",
          },
          frontmatter: {
            type: "object",
            description:
              'A key-value dictionary representing frontmatter fields (e.g. name, category, status, publish_at). Note: This must be a JSON object (Python dict / JavaScript object), not a YAML string. Example: {"name": "Title", "status": "published", "publish_at": "2026-07-28T16:00:00Z", "category": "Winter"}',
          },
          body: {
            type: "string",
            description: "The raw markdown content body",
          },
          composite: {
            type: "boolean",
            default: false,
            description: "Whether the page is composite",
          },
          partials: {
            type: "object",
            additionalProperties: { type: "string" },
            description: "Optional map of fragment slugs to fragment bodies",
          },
          expected_version: {
            type: "string",
            description:
              "Optional opaque version token from a prior read_page_metadata or read_page_content response (`version` field). A mismatch is rejected with 409 version_conflict unless `force` is true. Omit to write unconditionally.",
          },
          syntax_guide: {
            type: "string",
            description:
              "Document-specific formatting rules, shortcodes, or conventions to follow. This is populated by the system or editor context to guide the generated syntax.",
          },
        },
        required: ["slug", "frontmatter", "body"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "write_media_file",
      description: "Upload a media file via base64-encoded content.",
      parameters: {
        type: "object",
        properties: {
          filename: {
            type: "string",
            description:
              "The file name including directory structure (e.g., 'images/content/photo.jpg')",
          },
          content_base64: {
            type: "string",
            description: "The base64 encoded content of the file",
          },
        },
        required: ["filename", "content_base64"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "split_section",
      description:
        "Split a heading section from the currently open document or a partial into a new child fragment. Converts the page to a composite page if it is not already. Updates parent references, frontmatter, and partial composition in one transaction on the server.",
      parameters: {
        type: "object",
        properties: {
          slug: {
            type: "string",
            description:
              "The page identifier slug (must match Currently Open Document's Slug).",
          },
          source_slug: {
            type: "string",
            description:
              "The slug of the fragment to split (e.g. 'summary' or 'index').",
          },
          split_marker: {
            type: "string",
            description:
              "The exact text at which to split. Can be a heading (e.g., '## My Heading') or the exact starting text of a paragraph. Optional if the fragment has exactly two paragraphs.",
          },
          new_fragment_slug: {
            type: "string",
            description:
              "The slug/id of the new fragment to create (e.g. 'performance'). Do NOT include a leading underscore.",
          },
        },
        required: ["slug", "source_slug", "new_fragment_slug"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "merge_sections",
      description:
        "Merge one or more fragments into another fragment or back into the main/index post body. Validates composition rules and removes the merged fragments.",
      parameters: {
        type: "object",
        properties: {
          slug: {
            type: "string",
            description:
              "The page identifier slug (must match Currently Open Document's Slug).",
          },
          fragment_slugs: {
            type: "array",
            items: { type: "string" },
            description:
              "A list of fragment slugs/ids to merge (e.g., ['background-info', 'primer']). Do NOT include leading underscores.",
          },
          into_slug: {
            type: "string",
            description:
              "The target fragment slug/id to merge into, OR 'index' to merge back into the main document body. Do NOT include a leading underscore.",
          },
        },
        required: ["slug", "fragment_slugs", "into_slug"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "move_section",
      description: "Reorder sections/fragments within a composite document.",
      parameters: {
        type: "object",
        properties: {
          slug: {
            type: "string",
            description:
              "The page identifier slug (must match Currently Open Document's Slug).",
          },
          heading_path: {
            type: "string",
            description:
              "The fragment ID or heading title text of the section to move (e.g., 'performance'). Do NOT include a leading underscore.",
          },
          before_or_after: {
            type: "string",
            enum: ["before", "after"],
            description:
              "Whether to place the section before or after the target section.",
          },
          target_heading_path: {
            type: "string",
            description:
              "The fragment ID or heading title text of the target section (e.g., 'installation'). Do NOT include a leading underscore.",
          },
        },
        required: [
          "slug",
          "heading_path",
          "before_or_after",
          "target_heading_path",
        ],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "replace_selection",
      description:
        "Replace the currently SELECTED text in the active editor with new text. Only use this tool when the user has an active text selection — it is a no-op with no selection. Automatically snapshots state to the undo stack. For whole-document or no-selection edits, use write_content_file instead.",
      parameters: {
        type: "object",
        properties: {
          new_text: {
            type: "string",
            description: "The new text to replace the selection with.",
          },
          syntax_guide: {
            type: "string",
            description:
              "Document-specific formatting rules, shortcodes, or conventions to follow. This is populated by the system or editor context to guide the generated syntax.",
          },
        },
        required: ["new_text"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "insert_at_cursor",
      description:
        "Insert text content at the current cursor position in the active editor. Use for small, localized insertions when no text is selected. For whole-document rewrites or no-selection edits, use write_content_file with the full updated body. Automatically snapshots state to the undo stack.",
      parameters: {
        type: "object",
        properties: {
          content: {
            type: "string",
            description: "The content text to insert.",
          },
        },
        required: ["content"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "update_frontmatter_field",
      description:
        "Update a single metadata/frontmatter field of the current post (e.g. status, category, date, publish_at, deck, summary, faqs, hero_image, hero_title, trumpet, author, pinned). faqs is a list of {q, a} strings; pass [] to clear. Empty list is valid. Do not derive faqs from [expand] or headings. To schedule a future go-live, set status to 'published' AND publish_at to a UTC ISO-8601 datetime ending in Z (two calls, or use write_content_file with both fields). Note: The public title/headline printed on the post page is 'hero_title'. The 'name' field is strictly the internal/SEO post title (somewhat akin to a slug or folder identifier). When the user asks to change the title/headline of the post, you MUST update 'hero_title' (not 'name'). For byline attribution use key 'author' with a site author display name from list_authors/create_author — never put a person name in 'name'. Do NOT set pinned to true unless the operator explicitly asks to pin a post. Automatically snapshots state to the undo stack.",
      parameters: {
        type: "object",
        properties: {
          key: {
            type: "string",
            description:
              "The frontmatter field key to update (e.g. 'hero_title' for public title/headline, 'name' for internal post title, 'author' for byline display name, 'publish_at' for scheduled go-live, 'faqs' for the Q&A list).",
          },
          value: {
            description:
              "The new value to set for the field. For publish_at, use UTC ISO-8601 ending in Z (e.g. 2026-07-28T16:00:00Z). For author, use a site author display name. For faqs, pass an array of {q, a} strings, or [] to clear.",
          },
        },
        required: ["key", "value"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "get_document_outline",
      description:
        "Retrieve the hierarchical heading outline (Markdown headers) of the active editor/document.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_selection_context",
      description:
        "Retrieve the currently selected text along with the surrounding text context (paragraphs before and after) for grounded editing.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "suggest_internal_links",
      description:
        "Suggest published internal pages for Markdown links OR [expand]/[embed] Nutshell shortcodes. Returns live-published targets only (respects publish_at). Each result includes suggested_text (good default for link label / expand text=), markdown_link, and expand_shortcode stub. For Nutshells prefer insert_expand_embed after picking a slug; for normal navigation use [text](slug) — do not force expand for every suggestion.",
      parameters: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description:
              "Optional search query (e.g. 'Finland', 'Santa', 'Sanremo'). If omitted, the tool uses surrounding context/selection in the editor to suggest related pages.",
          },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "insert_expand_embed",
      description:
        "Build a valid [expand] or [embed] shortcode and insert it at the selection or cursor. Validates the slug against the live published catalog (refuses unpublished/missing). Prefer this over hand-writing shortcodes. text= is the visible label; heading= is only an optional section slice on the target — never put the spoken label in heading. source=\"summary\" uses frontmatter summary; source=\"deck\" uses frontmatter deck (each with Read more). Never combine source with heading.",
      parameters: {
        type: "object",
        properties: {
          mode: {
            type: "string",
            enum: ["expand", "embed"],
            description: "expand = Nutshell (collapsed until click); embed = always visible inline.",
          },
          slug: {
            type: "string",
            description: "Published target page slug from suggest_internal_links.",
          },
          text: {
            type: "string",
            description:
              "Visible label for the expand trigger / editor chip. For expand, defaults to selection or catalog suggested_text when omitted.",
          },
          heading: {
            type: "string",
            description:
              "Optional exact section heading (or composite partial title) to slice from the target. Only set when the user asked for a specific section. Do not set with source.",
          },
          source: {
            type: "string",
            enum: ["deck", "summary"],
            description:
              "Optional body source. \"summary\" = frontmatter summary nutshell; \"deck\" = frontmatter deck nutshell. Both append a Read more link. Do not set with heading.",
          },
          placement: {
            type: "string",
            enum: ["selection", "cursor"],
            description:
              "selection = replace current selection; cursor = insert at cursor. If omitted: selection when text is selected, else cursor.",
          },
        },
        required: ["mode", "slug"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "check_expand_refs",
      description:
        "Validate [expand]/[embed] shortcodes in the current open document (main + partials) or in an optional markdown string. Flags missing or unpublished target slugs. Heading misses are not broken (PHP falls back to the whole post).",
      parameters: {
        type: "object",
        properties: {
          markdown: {
            type: "string",
            description:
              "Optional markdown to check instead of the open editor body. Use before write_content_file to self-check a draft.",
          },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "list_page_headings",
      description:
        "List H1–H3 headings (and composite partial titles) from a target page. Use before insert_expand_embed when the user wants a section Nutshell so heading= matches a real heading.",
      parameters: {
        type: "object",
        properties: {
          slug: {
            type: "string",
            description: "Page slug to inspect.",
          },
        },
        required: ["slug"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "commit_and_push",
      description:
        "Stage, commit, and optionally push changes to the git remote. Rejects empty messages. Can use dry_run: true to preview the staged diff before actually committing. Always use dry_run first if the user asks 'show me what changed'.",
      parameters: {
        type: "object",
        properties: {
          message: { type: "string", description: "The commit message" },
          paths: {
            type: "array",
            items: { type: "string" },
            description:
              "Specific paths to stage. If empty, stages all changes.",
          },
          push: { type: "boolean", description: "Whether to push to remote." },
          dry_run: {
            type: "boolean",
            description: "If true, returns the staged diff without committing.",
          },
        },
        required: ["message"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "generate_media",
      description:
        "Generate an image via a configured model preset and store it in the media library. Returns relative_path / use_for_embedding (copy these into [image src=\"...\"] shortcodes and frontmatter fields like hero_image / main_image — never invent filenames) and public_url (chat preview only: ![alt](public_url)). The image is saved automatically; do NOT call attach_image_to_post for these.",
      parameters: {
        type: "object",
        properties: {
          prompt: {
            type: "string",
            description: "The detailed prompt for the image generator.",
          },
          filename: {
            type: "string",
            description:
              "The filename to save the image as (e.g. 'images/content/photo.png'). Ensure correct extension.",
          },
          preset: { type: "string", description: "Optional preset name." },
          alt_text: { type: "string", description: "Optional alt text." },
        },
        required: ["prompt", "filename"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "review_post",
      description:
        "Evaluate a post against the site's quality checklist. Returns a structured scorecard with per-criterion scores, notes, and suggested improvements. Use this when the user asks to review, evaluate, or check if a post is ready for publishing.",
      parameters: {
        type: "object",
        properties: {
          slug: {
            type: "string",
            description: "The slug of the post to evaluate. Defaults to the currently open document.",
          },
          checklist: {
            type: "string",
            description: "Optional ad-hoc checklist to evaluate against. If omitted, uses the site's stored quality checklist from settings.",
          },
        },
        required: ["slug"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "list_authors",
      description:
        "List site authors / contributor bios for the active content site (authors.yaml). Prefer this before creating a new author. Bios are plain text. To attribute the open post, set frontmatter key 'author' to an author's display name via update_frontmatter_field — never put a person name in post 'name' (that is the post title).",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_author",
      description: "Get one site author by slug.",
      parameters: {
        type: "object",
        properties: {
          slug: {
            type: "string",
            description: "Author slug (immutable id in authors.yaml).",
          },
        },
        required: ["slug"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "create_author",
      description:
        "Create a site author / contributor bio (plain text only — no Markdown). After create, attribute the open post by calling update_frontmatter_field with key 'author' and value equal to this author's display name (not the slug, and never post 'name').",
      parameters: {
        type: "object",
        properties: {
          name: {
            type: "string",
            description: "Display name used as the post byline string.",
          },
          slug: {
            type: "string",
            description: "Optional slug; derived from name when omitted.",
          },
          bio: {
            type: "string",
            description: "Plain-text bio (no Markdown rendering).",
          },
          website: { type: "string", description: "Optional website URL." },
          email: { type: "string", description: "Optional email." },
          role: { type: "string", description: "Optional role label." },
          sort_order: {
            type: "integer",
            description: "Optional sort order (lower first).",
          },
        },
        required: ["name"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "update_author",
      description:
        "Partial update of a site author bio. Slug is immutable (path only). Bios remain plain text. If you rename the display name and the open post should keep that author, also update frontmatter 'author' to the new name.",
      parameters: {
        type: "object",
        properties: {
          slug: {
            type: "string",
            description: "Author slug to update (immutable).",
          },
          name: { type: "string", description: "New display name." },
          bio: { type: "string", description: "Plain-text bio." },
          website: { type: "string" },
          email: { type: "string" },
          role: { type: "string" },
          sort_order: { type: "integer" },
        },
        required: ["slug"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "delete_author",
      description:
        "Delete a site author by slug. Does not clear post bylines that still reference the deleted display name.",
      parameters: {
        type: "object",
        properties: {
          slug: {
            type: "string",
            description: "Author slug to delete.",
          },
        },
        required: ["slug"],
      },
    },
  },
];

if (window.PenAiHandoff && window.PenAiHandoff.TOOL_DEFINITION) {
  TOOL_DEFINITIONS.push(window.PenAiHandoff.TOOL_DEFINITION);
}

const MCP_TOOL_MAP = {
  get_site_config: { method: "GET", path: "/mcp/site-config" },
  list_collections: { method: "GET", path: "/mcp/collections" },
  list_collection_entries: {
    method: "GET",
    path: "/mcp/collections/{collection_name}/entries",
  },
  read_page_metadata: { method: "GET", path: "/mcp/pages/{slug}/metadata" },
  read_page_content: { method: "GET", path: "/mcp/pages/{slug}/content" },
  search_content: { method: "GET", path: "/mcp/search" },
  list_media: { method: "GET", path: "/mcp/media" },
  write_content_file: { method: "PUT", path: "/mcp/pages/{slug}" },
  create_post: { method: "POST", path: "/mcp/posts" },
  write_media_file: { method: "POST", path: "/mcp/media" },
  split_section: { method: "POST", path: "/mcp/pages/{slug}/split" },
  merge_sections: { method: "POST", path: "/mcp/pages/{slug}/merge" },
  move_section: { method: "POST", path: "/mcp/pages/{slug}/move" },
  commit_and_push: { method: "POST", path: "/mcp/publish" },
  generate_media: { method: "POST", path: "/mcp/media/generate" },
  review_post: { method: "POST", path: "/mcp/pages/{slug}/review" },
  list_authors: { method: "GET", path: "/mcp/authors" },
  get_author: { method: "GET", path: "/mcp/authors/{slug}" },
  create_author: { method: "POST", path: "/mcp/authors" },
  update_author: { method: "PUT", path: "/mcp/authors/{slug}" },
  delete_author: { method: "DELETE", path: "/mcp/authors/{slug}" },
};

document.addEventListener("alpine:init", () => {
  Alpine.data("aiSidebar", () => ({
    // State variables
    messages: [],
    mediaCacheBusters: {},
    prompt: "",
    attachedFiles: [],
    attachedImages: [],
    streaming: false,
    streamingWord: 'STREAMING...',
    _streamingWordTimer: null,
    _streamingWords: [
      'STREAMING...', 'SLEUTHING...', 'THINKING...', 'FIGURING...',
      'HONING...', 'CRYSTALLIZING...', 'PICTURING...', 'PONDERING...',
      'FATHOMING...', 'SIFTING...', 'MULLING...', 'WEIGHING...',
      'UNTANGLING...', 'MUSING...',
    ],
    vaultUnlocked: false,
    vaultPassword: "",
    showVaultPassword: false,
    vaultUnlockError: "",
    isUnlockingVault: false,
    copiedMessageIndex: null,
    siteName: "PenCMS",
    siteId: "default",
    siteUrl: "http://localhost:8000",
    incomingHandoff: null,
    _handoffForThisTurn: null,
    _handoffTurnActive: false,
    pendingOutgoingHandoff: null,
    _handoffConfirmBusy: false,
    _handoffNavigating: false,
    abortController: null,
    // Cached /api/ai/schemas response. `null` = "not fetched yet";
    // the prompt builder treats null as "fall back to legacy hardcoded
    // behavior" so a schemas-endpoint outage never blocks writing.
    schemas: null,
    aiSettings: null,
    _pendingToolCalls: {},
    undoStack: [],
    session_context: [],
    tokenWarningModalOpen: false,
    tokenWarningCount: 0,
    tokenWarningResolve: null,
    _lastSelectionRange: null,

    activeSiteId() {
      try {
        const app = window.Alpine && Alpine.store("app");
        if (app && app.activeSiteId) {
          return String(app.activeSiteId).trim() || "default";
        }
      } catch (e) {}
      if (window.AUTH && window.AUTH.siteId) {
        return String(window.AUTH.siteId).trim() || "default";
      }
      return "default";
    },

    chatStorageKey(base) {
      return `${base}:${this.activeSiteId()}`;
    },

    syncSiteContext() {
      this.siteId = this.activeSiteId();
      try {
        const app = window.Alpine && Alpine.store("app");
        if (app && typeof app.resolveActiveSitename === "function") {
          this.siteName = app.resolveActiveSitename();
        } else if (app && app.sitename) {
          this.siteName = app.sitename;
        }
      } catch (e) {
        /* keep previous siteName */
      }
    },

    loadChatStateForSite() {
      const currentSlug =
        new URLSearchParams(window.location.search).get("id") || "";
      const slugKey = this.chatStorageKey("pen_undo_slug");
      const storedSlug = sessionStorage.getItem(slugKey);
      if (storedSlug !== currentSlug) {
        sessionStorage.removeItem(this.chatStorageKey("pen_undo_stack"));
        this.undoStack = [];
        sessionStorage.removeItem(this.chatStorageKey("pen_messages"));
        this.messages = [];
        sessionStorage.removeItem(this.chatStorageKey("pen_session_context"));
        this.session_context = [];
      } else {
        try {
          const storedStack = sessionStorage.getItem(
            this.chatStorageKey("pen_undo_stack"),
          );
          this.undoStack = storedStack ? JSON.parse(storedStack) : [];
        } catch (e) {
          this.undoStack = [];
        }
        try {
          const storedMessages = sessionStorage.getItem(
            this.chatStorageKey("pen_messages"),
          );
          this.messages = storedMessages ? JSON.parse(storedMessages) : [];
        } catch (e) {
          this.messages = [];
        }

        // Rebuild media URL cache-busters from stored tool results so that
        // persisted chat bubbles still show fresh thumbnails after reload.
        try {
          for (const msg of this.messages) {
            if (!msg || !msg.toolResults) continue;
            for (const tr of msg.toolResults) {
              if (!tr || !tr.result) continue;
              try {
                const parsed =
                  typeof tr.result === "string"
                    ? JSON.parse(tr.result)
                    : tr.result;
                if (parsed && parsed.url) {
                  this._mediaUrlVersions =
                    this._mediaUrlVersions || {};
                  this._mediaUrlVersions[parsed.url] = Date.now();
                }
              } catch (_) {}
            }
          }
        } catch (_) {}

        try {
          const storedContext = sessionStorage.getItem(
            this.chatStorageKey("pen_session_context"),
          );
          this.session_context = storedContext
            ? JSON.parse(storedContext)
            : [];
        } catch (e) {
          this.session_context = [];
        }
      }
      sessionStorage.setItem(slugKey, currentSlug);
    },

    async init() {
      this.syncSiteContext();
      this.loadChatStateForSite();
      this.consumeIncomingHandoff("editor");

      if (window.VAULT) {
        window.VAULT.ready.then(() => {
          this.vaultUnlocked = window.VAULT.unlocked;
        });

        // Also listen for custom events if you ever unlock without reloading
        window.addEventListener("pen:vault-unlocked", () => {
          this.vaultUnlocked = true;
        });
      }

      try {
        this.$watch(
          () => {
            const app = window.Alpine && Alpine.store("app");
            return (app && app.activeSiteId) || "default";
          },
          (next, prev) => {
            if (next === prev) return;
            this.syncSiteContext();
            this.loadChatStateForSite();
          },
        );
      } catch (e) {
        /* Alpine watch unavailable */
      }

      // Fetch AI schemas and settings in parallel.
      const apiBase = window.AUTH.apiBase.replace("/v1", "");
      const [schemasRes, settingsRes] = await Promise.allSettled([
        fetch(`${apiBase}/ai/schemas`, { headers: window.AUTH.getHeaders() }),
        fetch(`${apiBase}/ai/settings`, { headers: window.AUTH.getHeaders() }),
      ]);

      if (schemasRes.status === "fulfilled" && schemasRes.value.ok) {
        try {
          this.schemas = await schemasRes.value.json();
        } catch (e) {
          console.warn("Could not parse AI schemas response", e);
        }
      }
      if (settingsRes.status === "fulfilled" && settingsRes.value.ok) {
        try {
          this.aiSettings = await settingsRes.value.json();
        } catch (e) {
          console.warn("Could not parse AI settings response", e);
        }
      }
      this.siteUrl = window.location.origin;
      this.syncSiteContext();

      // Listen to window-level AI toggle event
      window.addEventListener("toggle-ai-sidebar", () => {
        const wizard = window.Alpine && Alpine.$data(document.body);
        if (wizard && wizard.workspacePrefs) {
          if (wizard.workspacePrefs.aiAssistantCollapsed) {
            this.openSidebar();
          } else {
            this.closeSidebar();
          }
        }
      });

      // Watch for state changes to trigger UI focus, scroll, and vault checks
      // Note: workspacePrefs inherits scope from the parent (wizard4) component
      this.$watch("workspacePrefs.aiAssistantCollapsed", (collapsed) => {
        if (!collapsed) {
          this.vaultUnlocked = window.VAULT?.unlocked || false;
          this.$nextTick(() => {
            const input = document.getElementById("ai-prompt-textarea");
            if (input) {
              input.focus();
              this.autoGrow(input);
            }
            this.scrollToBottom();
          });
        }
      });

      // Escape key listener (active only when accordion body has focus/containment)
      window.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        const wizard = window.Alpine && Alpine.$data(document.body);
        if (
          !wizard ||
          !wizard.workspacePrefs ||
          wizard.workspacePrefs.aiAssistantCollapsed
        )
          return;

        const target = e.target;
        const aiCard = document.getElementById("ai-chat-messages-container");
        const promptInput = document.getElementById("ai-prompt-textarea");
        if (
          (aiCard && aiCard.contains(target)) ||
          target === promptInput ||
          (promptInput && promptInput.contains(target))
        ) {
          e.preventDefault();
          e.stopPropagation();
          this.closeSidebar();
        }
      });

      // Listen to command dispatch event (e.g. from Ctrl+K overlay)
      window.addEventListener("pen:ai-command", async (e) => {
        const { command, selection, selectionRange } = e.detail || {};
        if (!command) return;

        this.openSidebar();

        // Format command text with selection context if present (avoiding italics)
        let formattedPrompt = command;
        if (selection) {
          formattedPrompt = `${command}\n\n---\n**Selected text context:**\n\`\`\`\n${selection}\n\`\`\``;
        }

        // Store the selection range passed from the overlay event
        this._lastSelectionRange =
          selectionRange || this.captureActiveSelectionRange();

        // Set prompt and trigger agent loop
        this.prompt = formattedPrompt;
        await this.sendPrompt(true);

        // Scroll the accordion card into viewport with smooth action
        this.$nextTick(() => {
          const accordionCard = document.querySelector(
            "[data-ai-accordion-card]",
          );
          if (accordionCard) {
            accordionCard.scrollIntoView({
              behavior: "smooth",
              block: "nearest",
            });
          }
        });
      });
    },

    async unlockVault() {
      if (!this.vaultPassword.trim() || !window.VAULT) return;

      this.isUnlockingVault = true;
      this.vaultUnlockError = "";

      try {
        await window.VAULT.unlock(this.vaultPassword);
        this.vaultUnlocked = true;
        this.vaultPassword = "";

        // Dispatch event in case other components need to know
        window.dispatchEvent(new CustomEvent("pen:vault-unlocked"));
        this.showToast("Vault unlocked successfully");

        this.$nextTick(() => {
          const input = document.getElementById("ai-prompt-textarea");
          if (input) input.focus();
        });
      } catch (e) {
        this.vaultUnlockError = "Incorrect password";
        this.$refs.vaultPasswordInput?.focus();
      } finally {
        this.isUnlockingVault = false;
      }
    },

    showToast(message, type = "success") {
      window.dispatchEvent(
        new CustomEvent("pen:toast", { detail: { message, type } }),
      );
    },

    openModalImage(url) {
      const wizard = window.Alpine && Alpine.$data(document.body);
      if (wizard && typeof wizard.openModal === "function") {
        const filename = url.split("/").pop();
        wizard.openModal({
          url: url,
          filename: filename,
          path: url.replace(
            /^\/(api\/v1\/media\/files|api\/assets\/raw)\//,
            "",
          ),
        });
      }
    },

    async regenerateMedia(toolCallId, event) {
      const btn = event.currentTarget;
      if (btn.disabled) return;

      let prompt = "";
      let filename = "";
      if (toolCallId) {
        for (const m of this.messages) {
          if (m.tool_calls) {
            const tc = m.tool_calls.find((t) => t.id === toolCallId);
            if (tc) {
              try {
                const args = JSON.parse(tc.function.arguments);
                prompt = args.prompt;
                filename = args.filename;
              } catch (e) {}
              break;
            }
          }
        }
      }

      if (!prompt || !filename) {
        this.showToast(
          "Could not find the original prompt or filename for regeneration.",
          "error",
        );
        return;
      }

      // Note: executeMcpToolOnServer now auto-appends a unique suffix to the
      // filename for generate_media calls, so no manual suffix is needed here.

      const originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = `
        <svg class="w-3 h-3 animate-spin text-forge-black shrink-0" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
        </svg>
        <span>Regenerating...</span>
      `;

      try {
        const result = await this.executeMcpToolOnServer("generate_media", {
          prompt,
          filename,
        });
        if (result && !result.error) {
          // Force reload in Alpine Media Gallery
          const wizard = window.Alpine && Alpine.$data(document.body);
          if (wizard && typeof wizard.loadAssets === "function") {
            await wizard.loadAssets();
          }

          // Update the message history with the new result content (so the chat thumbnail gets the new path)
          for (let i = 0; i < this.messages.length; i++) {
            if (this.messages[i].tool_call_id === toolCallId) {
              this.messages[i].content = JSON.stringify(result);
              break;
            }
          }

          // Update the cache-busting timestamp as fallback
          this.mediaCacheBusters = {
            ...this.mediaCacheBusters,
            [toolCallId]: Date.now(),
          };

          // Record the new URL so the Markdown image renderer can
          // cache-bust it if the LLM reuses the same path in its text.
          if (result.public_url) {
            _mediaUrlBusters.set(result.public_url.split("?")[0], Date.now());
          }

          this.saveMessages();

          this.showToast("Media regenerated successfully.");
        } else {
          this.showToast(result?.error || "Regeneration failed.", "error");
        }
      } catch (e) {
        this.showToast(`Regeneration failed: ${e.message}`, "error");
      } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
      }
    },

    captureActiveSelectionRange() {
      const editor = window.getPenEditor?.();
      const view = editor?.getView?.();
      const selection = view?.state?.selection?.main;
      if (selection && !selection.empty) {
        return {
          from: selection.from,
          to: selection.to,
          editorName:
            (window.Alpine && Alpine.$data(document.body)?.activePartial) ||
            "main",
        };
      }
      return null;
    },

    closeSidebar() {
      const wizard = window.Alpine && Alpine.$data(document.body);
      if (wizard && wizard.workspacePrefs) {
        wizard.workspacePrefs.aiAssistantCollapsed = true;
        wizard.saveWorkspacePrefs();
      }
      this.cleanup();
    },

    openSidebar() {
      const wizard = window.Alpine && Alpine.$data(document.body);
      if (wizard && wizard.workspacePrefs) {
        wizard.workspacePrefs.aiAssistantCollapsed = false;
        wizard.saveWorkspacePrefs();
      }
    },

    cleanup() {
      if (this.abortController) {
        this.abortController.abort();
        this.abortController = null;
      }
      this.streaming = false;
      this._stopStreamingWordCycle();
      this.attachedFiles = [];
      this.attachedImages = [];
      this.focusPrompt();
    },

    /**
     * Start cycling the streaming status word every 3–5 s (random jitter).
     * Always begins with "STREAMING..." so the first impression is clear.
     */
    _startStreamingWordCycle() {
      this._stopStreamingWordCycle();          // guard against double-start
      this.streamingWord = 'STREAMING...';
      const tick = () => {
        const delay = 3000 + Math.random() * 2000;   // 3 000 – 5 000 ms
        this._streamingWordTimer = setTimeout(() => {
          // Pick a word that differs from the current one
          const pool = this._streamingWords.filter(w => w !== this.streamingWord);
          this.streamingWord = pool[Math.floor(Math.random() * pool.length)];
          tick();                                     // schedule next swap
        }, delay);
      };
      tick();
    },

    /** Stop cycling and reset the displayed word. */
    _stopStreamingWordCycle() {
      if (this._streamingWordTimer) {
        clearTimeout(this._streamingWordTimer);
        this._streamingWordTimer = null;
      }
      this.streamingWord = 'STREAMING...';
    },

    // Simple frontmatter YAML parser for top-level scalar keys
    parseSimpleFrontmatter(yamlStr) {
      const obj = {};
      if (!yamlStr) return obj;
      const lines = yamlStr.split("\n");
      for (const line of lines) {
        const colonIdx = line.indexOf(":");
        if (colonIdx === -1) continue;
        const key = line.slice(0, colonIdx).trim();
        let val = line.slice(colonIdx + 1).trim();

        // Strip quotes if wrapped
        if (val.startsWith('"') && val.endsWith('"')) {
          val = val.slice(1, -1);
        } else if (val.startsWith("'") && val.endsWith("'")) {
          val = val.slice(1, -1);
        }
        obj[key] = val;
      }
      return obj;
    },

    /**
     * Render a collection's frontmatter schema as a compact markdown list
     * for inclusion in the system prompt.
     *
     * For taxonomy_ref fields, the allowed terms are inlined from the
     * cached taxonomy vocabularies so the AI knows the exact valid
     * values, not just the vocab name. Only vocabularies referenced by
     * a taxonomy_ref field are pulled — not the entire taxonomy
     * (which would bloat the prompt).
     *
     * @param {string} collectionName - key into schemas.collections
     * @returns {string} markdown block, or '' if schemas not loaded
     */
    renderCollectionSchema(collectionName) {
      if (!this.schemas || !this.schemas.collections) return "";
      const coll = this.schemas.collections[collectionName];
      if (!coll || !coll.frontmatter) return "";

      const vocabularies = this.schemas.taxonomy?.vocabularies || {};
      const primaryVocabulary =
        this.schemas.taxonomy?.primary_vocabulary || null;
      const primaryTerms =
        primaryVocabulary && vocabularies[primaryVocabulary]
          ? vocabularies[primaryVocabulary].terms || []
          : [];

      const lines = coll.frontmatter.map((f) => {
        let line = `- ${f.name} (${f.type}`;
        if (f.values) line += `: ${f.values.join("|")}`;
        if (f.vocabulary) {
          // `vocabulary: primary` is a sentinel meaning "this field holds a term
          // from the site's primary_vocabulary" (taxonomy.yaml's top-level
          // primary_vocabulary key), NOT a vocabulary literally named "primary".
          // This avoids the name collision between the frontmatter field `category`
          // and the historical vocabulary also named `category` in taxonomy.yaml —
          // which is a separate vocabulary and not what the frontmatter field validates
          // against. Resolving it to the primary_vocabulary's terms here keeps the
          // advertised allowed-values list in sync with the backend's
          // `validate_category` (which checks config.PRIMARY_TERMS).
          const vocabName =
            f.vocabulary === "primary"
              ? primaryVocabulary || "(primary_vocabulary not set)"
              : f.vocabulary;
          line += ` → vocab '${vocabName}'`;
          // Inline the allowed terms so the AI knows the exact
          // valid values, not just the vocab name.
          const terms =
            f.vocabulary === "primary"
              ? primaryTerms
              : vocabularies[f.vocabulary]?.terms || [];
          if (Array.isArray(terms) && terms.length > 0) {
            line += ` [allowed: ${terms.join(", ")}]`;
          }
        }
        line += f.required ? ", required" : ", optional";
        if (f.default !== undefined && f.default !== null)
          line += `, default=${JSON.stringify(f.default)}`;
        line += `) — ${f.description || ""}`;
        return line;
      });

      let block = `## Collection Schema: ${coll.label || collectionName}\n`;
      block += `This document belongs to the "${collectionName}" collection (${coll.directory}).\n\n`;
      block += `### Frontmatter fields\n${lines.join("\n")}\n`;

      // Conditional-required note — teaches the AI not to suggest
      // publishing an post missing hero_title.
      if (coll.conditional_required) {
        const cond = coll.conditional_required;
        block += `\n### Conditional requirements\n`;
        block += `If you change \`status\` to one of [${cond.when_status_in.join(", ")}], `;
        block += `these fields also become required: ${cond.fields.join(", ")}.\n`;
      }

      return block;
    },

    getPromptTemplate() {
      return `You are a content writing and SEO assistant embedded in {{SITE_NAME}}.
You are focused on the content file the user has open right now, but you also have access to tools that allow you to search, query, read, and write files in the CMS. Use these tools whenever you need to fetch information from the site configuration, search other posts, list collection entries, or perform file writes. Do not refuse to query other documents — you have active tools like \`search_content\`, \`read_page_content\`, and \`write_content_file\` to do so.

## Peer surfaces (routing)
You are on the **Content Editor** surface. Tools on sibling admin pages are out of reach here — do not invent or call them.
- **Content Editor** (open a post/page under Posts or Pages): prose, SEO, media, authors, document writes.
- **Navigation** (admin → Navigation): Primary, Secondary, and Footer menu items.
- **Customize** (admin → Customize): Twig templates/partials and CSS in the site custom theme.
If the ask clearly belongs on another surface: say so before declining, name that admin destination, briefly what belongs there vs here, and call \`handoff_to_surface\` with a concise \`goal\` (and useful \`facts\`). That tool only prepares a handoff — the operator must Cancel or Continue in the UI; do not assume navigation happened. Do not pretend you can act on the other surface.

## Tool selection rules (read first)
These rules determine which tool to call for an edit. When in doubt, default to \`write_content_file\`.
- **Edits with no active selection** → call \`write_content_file\` with the slug from "Currently Open Document" below and the FULL updated body. This is the default for whole-document edits, additions, rewrites, and any change that isn't a targeted replacement of selected text. The full current body is already included in your context below under "Document Body" / "Main Body (index.md)" — use it as the base and emit the complete new body. Do NOT call \`read_page_content\` first; you already have it.
- **Edits to a user-selected text region** → call \`replace_selection\` with the new text. Only valid when the user has an active selection; the tool returns an error if there is none. If you are unsure whether the user has a selection, assume they do not and use \`write_content_file\`.
- **Small insertions at a specific cursor spot** → call \`insert_at_cursor\`. Useful when the user points at a specific location. For larger rewrites, prefer \`write_content_file\`.
- **Single frontmatter field changes** (status, category, publish_at, etc.) → call \`update_frontmatter_field\`. For body+frontmatter changes together, use \`write_content_file\`.
- **Scheduling a future go-live** (e.g. "publish next Tuesday at noon") → set \`status\` to \`published\` **and** \`publish_at\` to the computed UTC ISO-8601 instant (two \`update_frontmatter_field\` calls, or one \`write_content_file\` with both fields in frontmatter). Interpret relative times using the Operator Clock below.
- **Title vs Name:** The public title or headline printed on the post is \`hero_title\`. The \`name\` field is strictly the internal/SEO post title (somewhat akin to a slug or folder name). If the user asks to change the "title" or "headline" of the post, you MUST update the \`hero_title\` key (not \`name\`). Never put a person/contributor name in post \`name\` — that is not byline attribution.
- **Site authors & bylines:** Prefer \`list_authors\` and reuse an existing \`authors[].name\`. If missing, call \`create_author\` then set the open post’s byline with \`update_frontmatter_field\` key \`author\` = that display **name** (not the slug). Author tools manage plain-text bios; \`update_frontmatter_field\` / \`write_content_file\` only set the byline string — they do not replace bio CRUD. Do not invent slug-only bylines; do not raw-write \`authors.yaml\`.
- **Composite documents** → prefer \`write_content_file\` with the full \`body\` (and \`partials\` if fragment edits are needed) rather than mixing inline tools across fragments.
- **Suggesting internal links or Nutshells** → call \`suggest_internal_links\` to find live-published posts/pages. For a normal link, insert \`[label](slug)\` (or use \`markdown_link\` from the result). For a Nutshell/expand/embed: call \`insert_expand_embed\` (after \`list_page_headings\` if they named a section). Optionally call \`check_expand_refs\` after writing. Never invent slugs; never force expand when the user asked for a normal link.
- **Attaching user-uploaded images to the post** → call \`attach_image_to_post\` with the correct \`image_index\` (shown in the \`<attached_images>\` list) and a \`filename\`. This writes the image to the media gallery. It does NOT insert the image into the body — you must separately call \`write_content_file\` with the image shortcode (e.g. \`[image src="..." ...]\`) to add it to the post body. Only call this tool when the user explicitly asks you to include an attached image in the post or media gallery.
- **AI-generated images** → after calling \`generate_media\`, the image is already saved in the media gallery. Do NOT call \`attach_image_to_post\` for AI-generated images — that tool is only for user-uploaded attachments. **After generate_media, copy \`relative_path\` (or \`use_for_embedding\`) verbatim** into \`[image src="..."]\` via \`write_content_file\` **and** into frontmatter fields like \`hero_image\` / \`main_image\` — never invent basenames (e.g. \`hero.jpg\`) and never put \`public_url\` in body or frontmatter. If you want to show or preview the generated image directly to the user in your chat message response, use standard Markdown image syntax: \`![alt_text](public_url)\` (using the \`public_url\` returned by the tool).
- \`get_document_outline\` and \`get_selection_context\` are for grounding when context is ambiguous — the document body and frontmatter below are already in your prompt, so you usually do not need them before a write.

## Your Specialties
- Writing compelling, readable markdown content
- SEO optimization: meta descriptions (150-160 chars), title tags, header hierarchy, keyword placement
- Recommending internal linking and Nutshells (\`[expand]\` / \`[embed]\`): identifying opportunities to link to or in-place expand other published pages
- Content structure: logical heading flow, scannable paragraphs, effective use of lists
- Readability improvements: active voice, concise sentences, clear transitions
- Frontmatter optimization
- Markdown formatting best practices

## Editor Syntax Conventions (use these instead of standard Markdown)
PenCMS extends standard Markdown with custom shortcodes. Always prefer these custom shortcodes over standard Markdown where applicable:
- Images: [image src="..." align="center" size="full" alt="..." caption="..."] (supports size="full|medium|small", align="center|left|right")
  * **Note on Image Display contexts:** Use the \`[image src="relative_path"]\` custom shortcode syntax ONLY when writing/updating the post body (e.g. via \`write_content_file\`). Copy the same \`relative_path\` into frontmatter \`hero_image\` / \`main_image\` when setting those fields. For showing/rendering images inline in your assistant chat replies to the user, use standard Markdown image syntax \`![alt](public_url)\` with the returned \`public_url\`.
- Video/Audio: [video src="..." align="center" size="medium" caption="..."] (or [youtube src="..." ...]) and [audio src="..." caption="..."]
- Quotes/Blockquotes: Use [quote author="..." source="..."]...[/quote] or [blockquote author="..." source="..."]...[/blockquote] for citations.
- Pullquotes: Use [pullquote]...[/pullquote] for large, magazine-style pull-out quotes.
- Notice Callouts (Info & Warning Boxes):
  - Component shortcodes (Preferred for blocks with titles or collapsible content):
    * [info title="..." collapsible="true"]...[/info] for tips, notes, or info callouts.
    * [warning title="..." collapsible="false"]...[/warning] for critical alerts or warnings.
  - GitHub-style Alert Callouts (Alternative):
    > [!NOTE]
    > Useful info...
    (Supported types: [!NOTE], [!TIP], [!IMPORTANT], [!WARNING], [!CAUTION])
- Highlights: Use ==highlighted text== or [highlight]highlighted text[/highlight] to highlight inline or block text.
- **Internal links vs Nutshells (expand / embed):** When the user says "nutshell", "expand in place", "click to reveal", or wants a phrase to open another post without leaving the page, use \`[expand]\` — not a normal Markdown link. When they want another post always visible inline, use \`[embed]\`.
  - Normal navigation link: \`[Link Text](slug)\` (slug only — never invent paths).
  - Expand (Nutshell, collapsed until clicked): \`[expand slug="target-slug" text="visible label"]\`
  - Expand a **section** of the target: \`[expand slug="target-slug" text="visible label" heading="Exact Section Heading"]\`
  - Expand the target’s **Summary** nutshell: \`[expand slug="target-slug" text="visible label" source="summary"]\` (frontmatter summary + Read more; never combine with \`heading\`)
  - Expand the target’s **Deck** nutshell: \`[expand slug="target-slug" text="visible label" source="deck"]\` (frontmatter deck + Read more; never combine with \`heading\`)
  - Embed (always visible): \`[embed slug="target-slug"]\` or with a section: \`[embed slug="target-slug" heading="Exact Section Heading"]\`. Optional \`text\` only affects the editor chip, not the public embed body.
  - **\`text\`** = clickable / chip label (what the reader sees). **\`heading\`** = optional section to slice inside the target — never put display copy in \`heading\`. **\`source="summary"\`** / **\`source="deck"\`** = distinct frontmatter nutshell bodies (no cross-fallback).
  - Nutshell workflow: \`suggest_internal_links\` → (optional) \`list_page_headings\` when they ask for a section, or \`source: "summary"\` / \`source: "deck"\` for a nutshell → \`insert_expand_embed\` → optional \`check_expand_refs\`. Example: "put Finland as a nutshell next to the Santa text" → suggest Finland/Christmas slug → \`insert_expand_embed\` with mode=expand, text="Finland".

### Heading Convention
- Do NOT add a Markdown H1 (\`# Title\`) in the body. The \`name\` and/or \`hero_title\` frontmatter fields automatically generate the on-page H1.
- Do NOT start the body content with any heading or subheading (neither H1 nor H2). The post body should begin directly with introductory paragraph text.
- Use H2 (\`##\`) for subsequent top-level sections and H3 (\`###\`) for subsections. Adding a body H1 would create a duplicate and harm SEO.

## Current Site
- Site ID: {{SITE_ID}}
- Name: {{SITE_NAME}}
- URL: {{SITE_URL}}
- All MCP tools operate only on this Content site. Do not assume pages, menus, or assets from other sites exist or are writable.

{{CUSTOM_INSTRUCTIONS}}

{{GUARDRAILS}}

{{DOCUMENT_CONTEXT}}

{{SCHEMAS}}

{{SESSION_HISTORY}}

## Guidelines
- You have access to tools for querying and managing the CMS. Call these tools to search content, read page contents, and update files. Do not explain the tools to the user; just invoke them when needed. If your environment does not support native tool calling, you MUST output your tool calls in your text response using this exact JSON block format:
\`\`\`tool_call
{
  "name": "tool_name",
  "arguments": {
    "arg_name": "arg_value"
  }
}
\`\`\`
Do not output any text inside that code block. Only write one block per message.
- Always return content as valid markdown
- When suggesting SEO improvements, be specific — give the exact replacement text
- Keep meta descriptions between 150-160 characters
- Match the existing tone and voice of the content
- When rewriting sections, preserve the factual content; improve only the prose
- For frontmatter changes, output the exact key-value pairs to update
- Be concise. The user is looking at the editor — they want actionable edits, not essays about theory.`;
    },

    buildSystemPrompt(state) {
      this.syncSiteContext();
      const frontmatterObj = this.parseSimpleFrontmatter(state.frontmatter);
      const currentSlug = state.slug || "";
      const fmName = frontmatterObj.name || "";
      const fmHeroTitle = frontmatterObj.hero_title || "";
      const status = frontmatterObj.status || "draft";
      const category = frontmatterObj.category || "";
      const isPage = frontmatterObj.page === "true" || frontmatterObj.page === true;

      // Query complete document parts context (handles main content + supplemental fragments)
      const docContext = window.getPenDocumentContext
        ? window.getPenDocumentContext()
        : null;

      // Operator clock for relative scheduling ("next Tuesday at noon")
      const now = new Date();
      const operatorTz =
        Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      const utcNowIso = now.toISOString().replace(/\.\d{3}Z$/, "Z");
      const localNowParts = new Intl.DateTimeFormat("en-CA", {
        timeZone: operatorTz,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        weekday: "long",
      }).formatToParts(now);
      const part = (type) =>
        localNowParts.find((p) => p.type === type)?.value || "";
      const localNowStr = `${part("weekday")} ${part("year")}-${part("month")}-${part("day")} ${part("hour")}:${part("minute")}:${part("second")}`;

      let docCtx = `## Currently Open Document
Slug: ${currentSlug}
Frontmatter \`name\`: ${fmName || "(not set)"}
Frontmatter \`hero_title\`: ${fmHeroTitle || "(not set)"}
Status: ${status}
Topic/Category: ${category || "(not set)"}
Page: ${isPage ? "true" : "false"}

### Operator Clock
- Timezone: ${operatorTz}
- Current local time: ${localNowStr} (${operatorTz})
- Current UTC: ${utcNowIso}
Interpret relative times the user mentions (e.g. "next Tuesday at noon", "tomorrow at 9am") in the operator timezone above, then write \`publish_at\` as UTC ISO-8601 ending in \`Z\`.

### Frontmatter (raw YAML — current values on disk)
${state.frontmatter || "(empty)"}

### Frontmatter write rules
When writing or updating frontmatter, follow these rules exactly:
- \`name\` — the canonical post title. Used for the URL slug, the HTML \`<title>\` tag, and listing pages. This is the primary title field.
- \`hero_title\` — optional display-headline override. When present, this is the large visual headline readers see on the post page. The URL/SEO \`<title>\` still uses \`name\`. Only set \`hero_title\` if the user explicitly wants a display headline that differs from \`name\`.
- \`title\` — **legacy key, do not use.** The backend aliases \`title\` → \`name\` on input, but you must always write \`name\`, never \`title\`.
- \`page\` — boolean. Defaults to \`false\`. Set to \`true\` for static pages vs blog posts.
- \`pinned\` — boolean. Defaults to \`false\` (all posts are unpinned). When \`true\`, the post appears first in public listings (still ordered by date among pinned posts). **Never set \`pinned: true\` unless the operator explicitly asks to pin a post.** Do not pin posts on your own initiative.
- \`status\` defaults to \`stub\` for new documents. Valid values: stub, draft, unpublished, published.
- \`publish_at\` — ISO-8601 UTC go-live datetime ending in \`Z\` (e.g. \`2026-07-28T16:00:00Z\`). Distinct from \`date\` (display/sort dateline). When \`status\` is \`published\` and \`publish_at\` is in the future, the post is **Scheduled** (embargoed from public listings until that instant). Omitted or past \`publish_at\` → live immediately on publish. To schedule: set \`status\` to \`published\` **and** \`publish_at\` to the computed UTC instant (two \`update_frontmatter_field\` calls, or one \`write_content_file\` frontmatter object). To clear a schedule while staying published: set \`publish_at\` to empty.
- \`date\` — YYYY-MM-DD display/sort dateline. Do not confuse with \`publish_at\`. When \`publish_at\` is set and \`date\` is empty, the calendar day of \`publish_at\` is used automatically.
- \`domain\` defaults to \`blog\`. Do not set it unless the user asks.
- **Preserve existing fields.** When writing frontmatter, always preserve every field already present in the raw YAML above. Never drop fields you did not intentionally change.
- **Never invent values from prompt labels.** The labels in this prompt (like "Slug", "Status", "Topic/Category", "Page") are informational context for you. Do not copy them into frontmatter fields. If a field shows "(not set)", leave it absent unless the user asks you to set it.
`;

      if (
        docContext &&
        (docContext.main || Object.keys(docContext.partials).length > 0)
      ) {
        docCtx += `\n## Document Structure (All Composite Parts)\n`;
        docCtx += `\n### Main Body (index.md)\n${docContext.main || "(Empty)"}\n`;
        Object.entries(docContext.partials).forEach(([name, content]) => {
          docCtx += `\n### Fragment: _${name}.md\n${content || "(Empty)"}\n`;
        });
      } else {
        docCtx += `\n### Document Body\n${state.body || ""}\n`;
      }

      if (state.selection) {
        docCtx += `\n### Currently Selected Text / Focus Area\n${state.selection}\n`;
      } else {
        docCtx += `\n### Currently Selected Text / Focus Area\n(No text selected. The user is focused on the full document.)\n`;
      }

      // Sourced from AI schemas response
      const collectionName =
        (this.schemas?.collections &&
          Object.keys(this.schemas.collections)[0]) ||
        "posts";
      const schemaBlock = this.renderCollectionSchema(collectionName) || "";

      // Sourced from site settings
      let customInstructionsBlock = "";
      const customInst =
        (window.Alpine &&
          Alpine.$data(document.body)?.settings?.ai_custom_instructions) ||
        "";
      if (customInst && customInst.trim()) {
        customInstructionsBlock = `## Custom Writing Instructions (set by site owner)\n${customInst.trim()}\n`;
      }

      // AI Agent Permissions & Guardrails
      let guardrailsBlock = "";
      if (this.aiSettings) {
        const publishAutonomy =
          this.aiSettings.ai_publish_autonomy || "require_approval";
        const metadataScope =
          this.aiSettings.ai_metadata_scope || "allow_metadata";
        const autoDeriveHero = false;
        const preventEmptyMedia = true;

        guardrailsBlock = `## AI Operation Guardrails\n`;
        if (publishAutonomy === "require_approval") {
          guardrailsBlock += `- **Publishing Autonomy**: You are NOT allowed to publish or unpublish posts. If you write or update the status field, you MUST set it to 'draft' or 'stub'. Leave publishing/unpublishing to human review.\n`;
        } else if (publishAutonomy === "restricted") {
          guardrailsBlock += `- **Publishing Autonomy**: You are strictly prohibited from changing or writing the 'status' field. Do not include 'status' in any frontmatter updates or tool calls. Status updates are human-only.\n`;
        } else {
          guardrailsBlock += `- **Publishing Autonomy**: You have full autonomy to publish or unpublish posts, pages, and translation siblings by setting the 'status' field to 'published', 'unpublished', 'draft', or 'stub'. i18n does not add a second review gate. When the user asks to schedule a future go-live, set \`status\` to \`published\` and \`publish_at\` to the computed UTC ISO-8601 instant (staggered publication).\n`;
        }

        if (metadataScope === "body_only") {
          guardrailsBlock += `- **Metadata Restriction**: You are strictly prohibited from modifying metadata / frontmatter. Do not call \`update_frontmatter_field\` or include frontmatter updates in \`write_content_file\`. Only modify the post body content.\n`;
        }

        if (autoDeriveHero) {
          guardrailsBlock += `- **Hero Title Derivation**: If you update or create the post name, but a \`hero_title\` is not set, you must automatically derive a suitable \`hero_title\` in the frontmatter.\n`;
        }

        if (preventEmptyMedia) {
          guardrailsBlock += `- **Media Integrity**: You must never write empty image \`src=""\` or placeholder image links. If image paths are unknown, use a valid placeholder image path or ask the user.\n`;
          guardrailsBlock += `- **Media paths after generate_media**: Always use the returned \`relative_path\` (or \`use_for_embedding\`) in \`[image src]\`, \`hero_image\`, and \`main_image\` — never invent filenames; never paste \`public_url\` into body or frontmatter.\n`;
        }
        guardrailsBlock += `- **Quality Review**: When the user asks to review, evaluate, or check if a post is ready for publishing, call the \`review_post\` tool with the current slug.\n`;
        guardrailsBlock += "\n";
      }

      // Compile system prompt template and substitute parameters
      let prompt = this.getPromptTemplate();
      prompt = prompt.replace(/\{\{SITE_ID\}\}/g, this.siteId || this.activeSiteId());
      prompt = prompt.replace(/\{\{SITE_NAME\}\}/g, this.siteName);
      prompt = prompt.replace(/\{\{SITE_URL\}\}/g, this.siteUrl);
      prompt = prompt.replace(/\{\{SCHEMAS\}\}/g, schemaBlock);
      prompt = prompt.replace(/\{\{DOCUMENT_CONTEXT\}\}/g, docCtx);
      prompt = prompt.replace(
        /\{\{CUSTOM_INSTRUCTIONS\}\}/g,
        customInstructionsBlock,
      );
      prompt = prompt.replace(/\{\{GUARDRAILS\}\}/g, guardrailsBlock);

      // Compile session history from session_context
      let sessionHistoryBlock = "";
      if (this.session_context && this.session_context.length > 0) {
        sessionHistoryBlock = `## Session History\nThe following edits/actions were performed in this session (newest last):\n${this.session_context
          .slice(-10)
          .map((item) => {
            const status = item.accepted
              ? "accepted"
              : "rejected/undone by user";
            const dateStr = new Date(item.timestamp).toLocaleTimeString();
            return `- [${dateStr}] Action: ${item.action} (${status}) — ${item.summary}`;
          })
          .join("\n")}\n`;
      }
      prompt = prompt.replace(/\{\{SESSION_HISTORY\}\}/g, sessionHistoryBlock);

      const handoff = this._handoffForThisTurn || this.incomingHandoff;
      if (handoff && window.PenAiHandoff) {
        prompt += window.PenAiHandoff.formatPromptBlock(handoff);
      }

      return prompt;
    },

    consumeIncomingHandoff(expectedTo) {
      if (!window.PenAiHandoff) return;
      const siteId = this.siteId || this.activeSiteId() || "default";
      const token = window.PenAiHandoff.consume(siteId, expectedTo);
      if (!token) return;
      this.incomingHandoff = token;
      this.openSidebar();
    },

    dismissIncomingHandoff() {
      this.incomingHandoff = null;
      this._handoffForThisTurn = null;
    },

    handoffFromLabel() {
      const from = this.incomingHandoff && this.incomingHandoff.from;
      if (!from) return "";
      return window.PenAiHandoff
        ? window.PenAiHandoff.surfaceLabel(from)
        : from;
    },

    beginHandoffNavigate(url, to) {
      this._handoffNavigating = true;
      const label = window.PenAiHandoff
        ? window.PenAiHandoff.surfaceLabel(to)
        : to;
      this.showToast(`Opening ${label}…`);
      setTimeout(() => {
        location.assign(url);
      }, 550);
    },

    shouldPauseStreamForHandoff() {
      return !!(this._handoffNavigating || this.pendingOutgoingHandoff);
    },

    isHandoffNavNoise(err) {
      if (!this._handoffNavigating) return false;
      if (!err) return true;
      if (err.name === "AbortError") return true;
      const msg = String(err.message || err);
      return /NetworkError|Failed to fetch|Load failed|fetch resource/i.test(
        msg,
      );
    },

    isOriginDirty() {
      try {
        const wizard = window.Alpine && Alpine.$data(document.body);
        return !!(wizard && wizard.saveStatus === "unsaved");
      } catch (e) {
        return false;
      }
    },

    async saveBeforeHandoff() {
      try {
        const wizard = window.Alpine && Alpine.$data(document.body);
        if (!wizard || typeof wizard.save !== "function") return true;
        await wizard.save({ silent: true });
        return wizard.saveStatus === "saved";
      } catch (e) {
        this.showToast(e.message || "Save failed.", "error");
        return false;
      }
    },

    outgoingHandoffLabel() {
      const to = this.pendingOutgoingHandoff && this.pendingOutgoingHandoff.to;
      if (!to) return "";
      return window.PenAiHandoff
        ? window.PenAiHandoff.surfaceLabel(to)
        : to;
    },

    cancelOutgoingHandoff() {
      if (window.PenAiHandoff) {
        window.PenAiHandoff.clear(this.siteId || this.activeSiteId() || "default");
      }
      this.pendingOutgoingHandoff = null;
      this._handoffConfirmBusy = false;
      this.showToast("Handoff cancelled — staying here.");
    },

    async confirmOutgoingHandoff() {
      const pending = this.pendingOutgoingHandoff;
      if (!pending || this._handoffConfirmBusy || this._handoffNavigating) return;

      const dirty = this.isOriginDirty();
      if (dirty) {
        if (pending.saveChoice !== "save" && pending.saveChoice !== "discard") {
          this.showToast("Choose whether to save your changes first.", "error");
          return;
        }
        if (pending.saveChoice === "save") {
          this._handoffConfirmBusy = true;
          try {
            const ok = await this.saveBeforeHandoff();
            if (!ok) return;
          } finally {
            this._handoffConfirmBusy = false;
          }
        }
      }

      const { url, to } = pending;
      this.pendingOutgoingHandoff = null;
      this.beginHandoffNavigate(url, to);
    },

    continueIncomingHandoff() {
      if (!this.incomingHandoff || this.streaming) return;
      const goal = (this.incomingHandoff.goal || "").trim();
      if (!goal) return;
      this.prompt = goal;
      this.sendPrompt();
    },

    handoff_to_surface(args) {
      if (!window.PenAiHandoff) {
        return { error: "Handoff helper unavailable." };
      }
      if (this.pendingOutgoingHandoff) {
        return {
          error:
            "A handoff is already waiting for confirmation. Ask the operator to Cancel or Continue first.",
        };
      }
      const siteId = this.siteId || this.activeSiteId() || "default";
      const result = window.PenAiHandoff.executeHandoff(
        args || {},
        "editor",
        siteId,
      );
      if (result.error) return result;
      this.pendingOutgoingHandoff = {
        to: result.to,
        url: result.url,
        goal: result.goal || (args && args.goal) || "",
        saveChoice: null,
      };
      this.openSidebar();
      this.showToast("Confirm handoff with Cancel or Continue below.");
      this.$nextTick(() => this.scrollToBottom());
      return {
        ok: true,
        pending_confirmation: true,
        to: result.to,
        message:
          "Handoff ready. Waiting for the operator to Cancel or Continue in the chat UI — do not assume navigation happened.",
      };
    },

    /**
     * Snapshot the live editor state (body, frontmatter, selection, slug)
     * for system-prompt assembly. Called once per streamCompletion
     * invocation so the LLM always sees the latest content — including
     * user edits made between turns and document mutations from tool calls
     * within the current turn.
     */
    getCurrentEditorState() {
      const editor = window.getPenEditor?.();
      if (!editor) return null;

      const state = editor.getMarkdownState();
      state.slug =
        state.slug ||
        new URLSearchParams(window.location.search).get("id") ||
        "";

      // The Traven editor only contains the body (no ---/YAML fences), so
      // state.frontmatter from getMarkdownState() is always empty.  The
      // actual frontmatter lives in the wizard4 form fields, exposed via
      // window.getPenFrontmatter().  Use it as the authoritative source.
      if (!state.frontmatter && window.getPenFrontmatter) {
        state.frontmatter = window.getPenFrontmatter();
      }

      // Editor buffer uses /api/assets/raw preview URLs; give the agent
      // canonical site-relative paths so writes do not round-trip them.
      const strip = window.fromEditorContentUrls;
      if (typeof strip === "function") {
        if (state.body) state.body = strip(state.body);
        if (state.selection) state.selection = strip(state.selection);
      }

      return state;
    },

    getSyntaxGuide(state) {
      if (!state || !state.frontmatter) return "";
      const frontmatterObj = this.parseSimpleFrontmatter(state.frontmatter);
      return frontmatterObj.syntax_guide || frontmatterObj.format_guide || "";
    },

    async sendPrompt(fromEvent = false) {
      if (
        (!this.prompt.trim() &&
          this.attachedFiles.length === 0 &&
          this.attachedImages.length === 0) ||
        this.streaming
      )
        return;

      if (!fromEvent) {
        this._lastSelectionRange = this.captureActiveSelectionRange();
      }

      // 1. Await vault readiness
      if (window.VAULT?.ready) await window.VAULT.ready;

      // 2. Check vault unlocked
      if (!window.VAULT?.unlocked) {
        this.showToast(
          "Unlock your vault under User Settings → Vault to use AI.",
          "error",
        );
        return;
      }

      // 3. Check AI config present
      const ai = window.VAULT.getSecret("AI_PROVIDER_CONFIG");
      if (!ai) {
        this.showToast(
          "Configure an AI provider in User Settings → Vault first.",
          "error",
        );
        return;
      }
      const isLocal = ai.baseUrl && /localhost|127\.0\.0\.1/i.test(ai.baseUrl);
      if (!isLocal && !ai.apiKey) {
        this.showToast(
          "Configure an AI provider in User Settings → Vault first.",
          "error",
        );
        return;
      }

      // 4. Check active editor
      const state = this.getCurrentEditorState();
      if (!state) {
        this.showToast("Open a document first.", "error");
        return;
      }

      const systemPrompt = this.buildSystemPrompt(state);

      // Estimate tokens
      let historyText = "";
      for (const msg of this.messages) {
        if (msg.content) {
          if (Array.isArray(msg.content)) {
            // Multimodal content array — estimate text parts, count images
            for (const part of msg.content) {
              if (part.type === "text" && part.text)
                historyText += part.text + " ";
            }
          } else {
            historyText += msg.content + " ";
          }
        }
        if (msg.tool_calls) historyText += JSON.stringify(msg.tool_calls) + " ";
      }
      const toolsText = JSON.stringify(TOOL_DEFINITIONS);
      const attachedChars = this.attachedFiles.reduce(
        (sum, f) => sum + f.content.length,
        0,
      );
      // Each image costs ~85 tokens (low-res) to ~1100 tokens (high-res).
      // Use the dynamically calculated estimatedTokens if available, otherwise fall back to 1000.
      const imageTokenEstimate = this.attachedImages.reduce(
        (sum, img) => sum + (img.estimatedTokens || 1000),
        0,
      );
      const totalChars =
        systemPrompt.length +
        historyText.length +
        this.prompt.length +
        attachedChars +
        toolsText.length;
      const tokenEstimate = Math.ceil(totalChars / 4) + imageTokenEstimate;

      // 5. Token budget guardrail (30,000 tokens ≈ 120,000 chars)
      if (tokenEstimate > 30000) {
        const confirmed = await this.showTokenWarningModal(tokenEstimate);
        if (!confirmed) return;
      }

      // Stage user prompt with attachments
      const validImages = this.attachedImages.filter(
        (img) => img.dataUrl && !img.encoding,
      );
      const hasImages = validImages.length > 0;
      const hasTextFiles = this.attachedFiles && this.attachedFiles.length > 0;

      // Build text parts for the content array
      let textBlock = "";
      if (hasTextFiles) {
        for (const file of this.attachedFiles) {
          textBlock += `<attached_file name="${file.name}">\n${file.content}\n</attached_file>\n\n`;
        }
      }
      // When images are attached, tell the LLM about them so it knows the
      // indices for the attach_image_to_post tool.
      if (hasImages) {
        const imgList = validImages
          .map(
            (img, i) =>
              `  [${i}] ${img.name} (${Math.round(img.size / 1024)} KB)`,
          )
          .join("\n");
        textBlock += `<attached_images>\nThe user has attached the following image(s). You can see them below. If the user asks to include one in the post, call the attach_image_to_post tool with the correct image_index.\n${imgList}\n</attached_images>\n\n`;
      }
      const userPromptText = this.prompt;
      textBlock += userPromptText;

      // Build the content payload: plain string when no images, array when images present
      let contentPayload;
      if (hasImages) {
        const parts = [];
        if (textBlock.trim()) {
          parts.push({ type: "text", text: textBlock });
        }
        for (const img of validImages) {
          parts.push({
            type: "image_url",
            image_url: { url: img.dataUrl, detail: "auto" },
          });
        }
        contentPayload = parts;
      } else {
        contentPayload = textBlock;
      }

      const userMessage = { role: "user", content: contentPayload };
      // Always set displayContent to userPromptText so raw XML blocks are not shown to the user
      userMessage.displayContent = userPromptText;
      if (hasImages) {
        userMessage.attachedImages = validImages.map((i) => ({
          name: i.name,
          dataUrl: i.dataUrl,
        }));
      }
      if (hasTextFiles) {
        userMessage.attachedFiles = this.attachedFiles.map((f) => ({
          name: f.name,
          sizeKb: Math.round(f.content.length / 100) / 10,
        }));
      }

      this.messages.push(userMessage);
      this.capMessages();
      this.saveMessages();
      this.prompt = "";
      this.attachedFiles = []; // Clear text files immediately since they are inlined into the message
      // NOTE: attachedImages persist across turns.
      // The LLM may call attach_image_to_post later in the conversation,
      // so the images must remain available. They are only cleared on
      // newConversation() or when the user removes them via the ✕ button.

      this.$nextTick(() => {
        this.scrollToBottom();
        const ta = document.getElementById("ai-prompt-textarea");
        if (ta) this.autoGrow(ta);
      });

      await this.streamCompletion();
    },

    async executeTool(functionName, args) {
      // Enforce client-side guardrails
      if (this.aiSettings) {
        const publishAutonomy =
          this.aiSettings.ai_publish_autonomy || "require_approval";
        const metadataScope =
          this.aiSettings.ai_metadata_scope || "allow_metadata";
        const preventEmptyMedia = true;

        if (functionName === "update_frontmatter_field") {
          if (args.key === "status") {
            if (publishAutonomy === "restricted") {
              return {
                error:
                  "Permission Denied: AI is prohibited from modifying the status field.",
              };
            }
            if (
              publishAutonomy === "require_approval" &&
              (args.value === "published" || args.value === "unpublished")
            ) {
              return {
                error:
                  "Permission Denied: AI is not allowed to set status to '" +
                  args.value +
                  "' without human approval. Please keep status as 'draft' or 'stub'.",
              };
            }
          }
          if (metadataScope === "body_only") {
            return {
              error:
                "Permission Denied: AI is restricted to body-only edits and cannot modify metadata.",
            };
          }
        }

        if (functionName === "write_content_file") {
          if (preventEmptyMedia && args.body) {
            if (
              /\[image[^\]]*src=(["'])\s*\1/.test(args.body) ||
              /\[image\s+[^\]]*src=\s*\]/.test(args.body) ||
              /!\[.*?\]\(\s*\)/.test(args.body)
            ) {
              return {
                error:
                  "Integrity Violation: Image source path cannot be empty. Ensure all [image src=\"...\"] shortcodes have a valid path.",
              };
            }
          }

          if (args.frontmatter) {
            const parentData = window.Alpine && Alpine.$data(document.body);
            const currentStatus =
              parentData && parentData.form ? parentData.form.status : "stub";

            if (metadataScope === "body_only") {
              if (parentData && parentData.form) {
                for (const [k, v] of Object.entries(args.frontmatter)) {
                  if (k === "slug") continue;
                  if (parentData.form[k] !== v) {
                    return {
                      error:
                        "Permission Denied: AI is restricted to body-only edits and cannot modify frontmatter.",
                    };
                  }
                }
              } else {
                if (
                  Object.keys(args.frontmatter).some(
                    (k) => k !== "name" && k !== "slug",
                  )
                ) {
                  return {
                    error:
                      "Permission Denied: AI is restricted to body-only edits.",
                  };
                }
              }
            }

            const newStatus = args.frontmatter.status;
            if (newStatus && newStatus !== currentStatus) {
              if (publishAutonomy === "restricted") {
                return {
                  error:
                    "Permission Denied: AI is prohibited from modifying the status field.",
                };
              }
              if (
                publishAutonomy === "require_approval" &&
                (newStatus === "published" || newStatus === "unpublished")
              ) {
                return {
                  error:
                    "Permission Denied: AI is not allowed to set status to '" +
                    newStatus +
                    "' without human approval. Please set status to 'draft' or 'stub'.",
                };
              }
            }
          }
        }
      }

      const clientTools = [
        "replace_selection",
        "insert_at_cursor",
        "update_frontmatter_field",
        "get_document_outline",
        "get_selection_context",
        "suggest_internal_links",
        "insert_expand_embed",
        "check_expand_refs",
        "list_page_headings",
        "attach_image_to_post",
        "handoff_to_surface",
      ];
      if (clientTools.includes(functionName)) {
        try {
          return await this[functionName](args);
        } catch (e) {
          return { error: `Failed to execute ${functionName}: ${e.message}` };
        }
      }

      if (functionName === "write_content_file") {
        try {
          const result = await this.writeContentFileOnServer(args);
          if (result && result.error_code === "version_conflict") {
            return result;
          }
          if (result && !result.error) {
            const editor = window.getPenEditor?.();
            const currentBody = editor ? editor.getValue() : "";
            const activePartial =
              (window.Alpine && Alpine.$data(document.body)?.activePartial) ||
              "main";
            const field = activePartial === "main" ? "body" : activePartial;

            const txId =
              "tx_" +
              Date.now() +
              "_" +
              Math.random().toString(36).substr(2, 6);
            this.pushToUndoStack({
              id: txId,
              field: field,
              previousValue: currentBody,
              timestamp: Date.now(),
            });

            this.addSessionContext(
              "write_content_file",
              `Updated content file "${args.slug}"`,
              true,
              txId,
            );

            await this.refreshEditorFromServer(args.slug);
          }
          return result;
        } catch (e) {
          return { error: `Failed to write content file: ${e.message}` };
        }
      }

      if (functionName === "create_post") {
        try {
          const result = await this.executeMcpToolOnServer(functionName, args);
          if (result && !result.error && result.slug) {
            this.addSessionContext(
              "create_post",
              `Created new post "${args.name}" (slug: ${result.slug})`,
              true
            );
            const wizard = window.Alpine && Alpine.$data(document.body);
            if (wizard && typeof wizard.loadPage === "function") {
              history.replaceState(null, "", (Alpine.store("app") && typeof Alpine.store("app").adminPath === "function")
                ? Alpine.store("app").adminPath("admin-editor.php", { id: result.slug })
                : `admin-editor.php?id=${encodeURIComponent(result.slug)}`);
              wizard.isNew = false;
              await wizard.loadPage(result.slug);
              if (typeof wizard.loadAssets === "function") {
                await wizard.loadAssets();
              }
            }
          }
          return result;
        } catch (e) {
          return { error: `Failed to create post: ${e.message}` };
        }
      }

      if (
        ["split_section", "merge_sections", "move_section"].includes(
          functionName,
        )
      ) {
        try {
          const wizard = window.Alpine && Alpine.$data(document.body);
          if (!wizard) {
            throw new Error("Alpine application context not found");
          }

          // Pre-save live editor state to disk so the backend tool operates on the latest changes
          if (typeof wizard.save === "function") {
            await wizard.save();
          }

          // Cleanly extract frontmatter metadata, stripping internal state keys to prevent python-frontmatter kwargs collision during undo
          const { content, composite, partials, id, frontmatter, ...metadata } =
            wizard.form;

          // Capture structural state snapshot BEFORE running the tool (for undo)
          const previousState = {
            frontmatter: JSON.parse(JSON.stringify(metadata)),
            content: window.getPenEditor?.("main")?.getValue() || "",
            composite: wizard.form.composite || false,
            partials: {},
          };
          if (wizard.form.partials) {
            Object.keys(wizard.form.partials).forEach((k) => {
              const ed = window.getPenEditor?.(k);
              previousState.partials[k] = ed
                ? ed.getValue()
                : wizard.form.partials[k];
            });
          }

          const result = await this.executeMcpToolOnServer(functionName, args);
          if (result && !result.error) {
            const txId =
              "tx_" +
              Date.now() +
              "_" +
              Math.random().toString(36).substr(2, 6);

            this.pushToUndoStack({
              id: txId,
              is_structural: true,
              slug: args.slug,
              previousState: previousState,
              timestamp: Date.now(),
            });

            this.addSessionContext(
              functionName,
              `Executed structural refactoring: ${functionName}`,
              true,
              txId,
            );

            await this.refreshEditorFromServer(args.slug);
          }
          return result;
        } catch (e) {
          return {
            error: `Failed to execute structural refactoring: ${e.message}`,
          };
        }
      }

      if (MCP_TOOL_MAP[functionName]) {
        try {
          const result = await this.executeMcpToolOnServer(functionName, args);
          if (
            ["generate_media", "write_media_file"].includes(functionName) &&
            result &&
            !result.error
          ) {
            const wizard = window.Alpine && Alpine.$data(document.body);
            if (wizard && typeof wizard.loadAssets === "function") {
              await wizard.loadAssets();
            }
            this.showToast("Media updated successfully.");
            // Record the generated URL so the Markdown image renderer can
            // cache-bust it if the LLM reuses the same path in its text.
            if (result.public_url) {
              _mediaUrlBusters.set(result.public_url.split("?")[0], Date.now());
            }
          }
          if (
            ["create_author", "update_author", "delete_author"].includes(
              functionName
            ) &&
            result &&
            !result.error
          ) {
            const wizard = window.Alpine && Alpine.$data(document.body);
            if (wizard && typeof wizard.loadAuthors === "function") {
              await wizard.loadAuthors();
            }
          }
          return result;
        } catch (e) {
          return { error: `Tool execution failed: ${e.message}` };
        }
      }

      return { error: `Tool not implemented yet: ${functionName}` };
    },

    async executeMcpToolOnServer(functionName, args) {
      return window.PenMcpClient.executeMcpTool({
        functionName,
        args,
        toolMap: MCP_TOOL_MAP,
        prepareArgs(fn, requestArgs) {
          // Auto-append unique suffix to filename for generate_media so that
          // every generation produces a distinct URL, preventing browser cache
          // collisions when the LLM reuses the same requested filename.
          if (fn === "generate_media" && requestArgs.filename) {
            const dotIdx = requestArgs.filename.lastIndexOf(".");
            const suffix =
              "-" +
              Math.floor(Date.now() / 1000)
                .toString()
                .slice(-5);
            if (dotIdx !== -1) {
              requestArgs.filename =
                requestArgs.filename.slice(0, dotIdx) +
                suffix +
                requestArgs.filename.slice(dotIdx);
            } else {
              requestArgs.filename = requestArgs.filename + suffix;
            }
          }
          return requestArgs;
        },
        enrichHeaders(fn, headers) {
          if (fn === "generate_media" && window.VAULT && window.VAULT.unlocked) {
            const imgConfig = window.VAULT.getSecret("AI_IMAGE_CONFIG");
            if (imgConfig) {
              if (imgConfig.apiKey)
                headers["X-Pen-AI-Image-Key"] = imgConfig.apiKey;
              if (imgConfig.baseUrl)
                headers["X-Pen-AI-Image-Base-URL"] = imgConfig.baseUrl;
              if (imgConfig.model)
                headers["X-Pen-AI-Image-Model"] = imgConfig.model;
            }
          }
          return headers;
        },
        async afterResponse(_fn, data, { apiBase, headers }) {
          if (data && data.task_id && data.status === "pushing") {
            while (data.status === "pushing" || data.status === "running") {
              await new Promise((r) => setTimeout(r, 1000));
              const pollResp = await fetch(
                `${apiBase}/mcp/publish/${data.task_id}`,
                { headers },
              );
              if (!pollResp.ok) {
                return { error: "Failed to poll push status" };
              }
              data = await pollResp.json();
            }
          }
          return data;
        },
      });
    },

    async refreshEditorFromServer(writtenSlug) {
      const openSlug =
        new URLSearchParams(window.location.search).get("id") || "";
      if (!openSlug || !writtenSlug) return;

      const normalizedWritten = String(writtenSlug).toLowerCase().trim();
      const normalizedOpen = String(openSlug).toLowerCase().trim();

      if (normalizedWritten !== normalizedOpen) {
        this.showToast(
          `Wrote ${writtenSlug} (not the open document ${openSlug}).`,
          "info",
        );
        return;
      }

      try {
        const wizard = window.Alpine && Alpine.$data(document.body);
        if (wizard && wizard.loadPage) {
          await wizard.loadPage(openSlug);

          // Wait for Alpine to process x-for DOM updates (adding/removing tabs)
          if (wizard.$nextTick) {
            await wizard.$nextTick();
          } else {
            await new Promise((r) => setTimeout(r, 50));
          }

          if (wizard.form.composite && wizard.form.partials) {
            for (const [name, content] of Object.entries(
              wizard.form.partials,
            )) {
              if (
                window._editors &&
                window._editors.partials &&
                window._editors.partials[name]
              ) {
                // Editor survived the refactoring, just update its content safely
                window._editors.partials[name].setValue(content);
              } else {
                // Newly created fragment, initialize a brand new editor
                if (typeof wizard._initPartialEditor === "function") {
                  await wizard._initPartialEditor(name);
                }
              }
            }
          }

          // Cleanup orphaned editors for fragments that were merged/deleted
          if (window._editors && window._editors.partials) {
            Object.keys(window._editors.partials).forEach((name) => {
              if (
                !wizard.form.partials ||
                wizard.form.partials[name] === undefined
              ) {
                if (
                  typeof window._editors.partials[name].destroy === "function"
                ) {
                  window._editors.partials[name].destroy();
                }
                delete window._editors.partials[name];
              }
            });
          }
        }
        this.showToast(`Saved and refreshed ${openSlug} from disk.`, "success");
      } catch (e) {
        console.warn("refreshEditorFromServer failed:", e);
      }
    },

    async restoreStructuralState(slug, previousState) {
      await this.writeContentFileOnServer({
        slug: slug,
        frontmatter: previousState.frontmatter,
        body: previousState.content,
        composite: previousState.composite,
        partials: previousState.partials,
      });
      await this.refreshEditorFromServer(slug);
    },

    async writeContentFileOnServer(args) {
      const { method, path } = MCP_TOOL_MAP["write_content_file"];
      let finalPath = path.replace("{slug}", encodeURIComponent(args.slug));
      const url = `${window.AUTH.apiBase}${finalPath}`;

      // Defense in depth: strip editor preview URLs before MCP write so
      // round-tripped /api/assets/raw paths never hit disk.
      const strip = window.fromEditorContentUrls;
      let body = args.body;
      let partials = args.partials || {};
      let frontmatter = args.frontmatter;
      if (typeof strip === "function") {
        if (typeof body === "string") body = strip(body);
        if (partials && typeof partials === "object") {
          const cleaned = {};
          for (const [k, v] of Object.entries(partials)) {
            cleaned[k] = typeof v === "string" ? strip(v) : v;
          }
          partials = cleaned;
        }
        if (frontmatter && typeof frontmatter === "object") {
          frontmatter = { ...frontmatter };
          for (const key of ["hero_image", "main_image"]) {
            if (typeof frontmatter[key] === "string") {
              frontmatter[key] = strip(frontmatter[key]);
            }
          }
        }
      }

      const bodyObj = {
        frontmatter,
        body,
        composite: args.composite || false,
        partials,
      };
      if (args.expected_version != null && args.expected_version !== "") {
        bodyObj.expected_version = args.expected_version;
      }
      if (args.force === true) {
        bodyObj.force = true;
      }

      const resp = await fetch(url, {
        method,
        headers: window.AUTH.getHeaders(),
        body: JSON.stringify(bodyObj),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        const detail = err && err.detail;
        if (
          resp.status === 409 &&
          detail &&
          typeof detail === "object" &&
          detail.error === "version_conflict"
        ) {
          return {
            error: detail.message || "version_conflict",
            error_code: "version_conflict",
            current_version: detail.current_version,
            expected_version: detail.expected_version,
          };
        }
        let errMsg = resp.statusText;
        if (detail) {
          errMsg =
            typeof detail === "object" ? JSON.stringify(detail) : detail;
        }
        throw new Error(errMsg);
      }
      return resp.json();
    },

    async streamCompletion() {
      if (this._handoffNavigating) return;

      const isOuter = !this._handoffTurnActive;
      if (isOuter) {
        this._handoffTurnActive = true;
        this._handoffForThisTurn = this.incomingHandoff;
        this.incomingHandoff = null;
      }

      this.streaming = true;
      this._startStreamingWordCycle();
      this.abortController = new AbortController();

      const apiBase = window.AUTH.apiBase.replace("/v1", "");

      // Rebuild the system prompt from live editor state on EVERY call
      // (including recursive iterations after tool calls). This guarantees
      // the LLM always sees the latest document content — whether the user
      // edited manually between turns, or a tool call mutated the file
      // within the current turn. For composite documents, this captures
      // the full content of index.md AND all partials (_*.md) every time.
      const state = this.getCurrentEditorState();
      const systemPrompt = state
        ? this.buildSystemPrompt(state)
        : "You are a content writing assistant. The editor state could not be read.";

      try {
        const payloadMessages = [{ role: "system", content: systemPrompt }];

        // Find the index of the most recent user message in history
        let lastUserIdx = -1;
        for (let i = this.messages.length - 1; i >= 0; i--) {
          if (this.messages[i].role === "user") {
            lastUserIdx = i;
            break;
          }
        }

        for (let idx = 0; idx < this.messages.length; idx++) {
          const msg = this.messages[idx];
          const m = { role: msg.role };
          if (msg.content !== undefined && msg.content !== null) {
            m.content = msg.content;
          }
          if (msg.name) {
            m.name = msg.name;
          }
          if (msg.tool_calls) {
            m.tool_calls = msg.tool_calls;
          }
          if (msg.tool_call_id) {
            m.tool_call_id = msg.tool_call_id;
          }

          // Truncate older tool messages to optimize prompt size and TTFT.
          // We only truncate tool messages from PREVIOUS user chat turns
          // (i.e. those that occurred before the most recent user message).
          if (msg.role === "tool" && idx < lastUserIdx && m.content) {
            try {
              const parsed = JSON.parse(m.content);
              if (parsed && typeof parsed === "object") {
                const summary = {};
                if (parsed.error) {
                  summary.status = "error";
                  summary.error =
                    typeof parsed.error === "string" &&
                    parsed.error.length > 150
                      ? parsed.error.substring(0, 150) + "..."
                      : parsed.error;
                } else {
                  summary.status = "success";
                  summary.info =
                    "Older tool response details omitted to optimize prompt size.";
                  // Preserve embed paths so later turns can still reference media.
                  if (parsed.relative_path) {
                    summary.relative_path = parsed.relative_path;
                  }
                  if (parsed.use_for_embedding) {
                    summary.use_for_embedding = parsed.use_for_embedding;
                  }
                  if (parsed.filename) {
                    summary.filename = parsed.filename;
                  }
                  // Soft write signals — stable schema so later turns / smoke
                  // tests always see total/capped/items (never a silent drop).
                  const isWriteTool = msg.name === "write_content_file";
                  const hasMediaWarns = Array.isArray(
                    parsed.media_path_warnings,
                  );
                  if (isWriteTool || hasMediaWarns || parsed.version_warning) {
                    // Single cap constant: capped === (items.length < total).
                    const MAX_MEDIA_PATH_WARNINGS = 20;
                    const warns = hasMediaWarns
                      ? parsed.media_path_warnings
                      : [];
                    const items = warns.slice(0, MAX_MEDIA_PATH_WARNINGS);
                    summary.media_path_warnings = {
                      total: warns.length,
                      capped: items.length < warns.length,
                      items,
                    };
                    // Parity: always include version_warning on write summaries
                    // (null when absent) so concurrency noise stays inspectable.
                    if (isWriteTool || parsed.version_warning) {
                      summary.version_warning = parsed.version_warning || null;
                    }
                  }
                }
                if (Array.isArray(parsed)) {
                  summary.results_count = parsed.length;
                } else if (parsed.results) {
                  summary.results_count = Array.isArray(parsed.results)
                    ? parsed.results.length
                    : 1;
                } else if (parsed.items) {
                  summary.results_count = parsed.items.length;
                } else if (parsed.headings) {
                  summary.results_count = parsed.headings.length;
                }
                m.content = JSON.stringify(summary);
              }
            } catch (e) {
              if (m.content.length > 100) {
                m.content =
                  m.content.substring(0, 100) +
                  "... [older response truncated]";
              }
            }
          }

          payloadMessages.push(m);
        }

        // Construct dynamic tools list to inject document-specific syntax overrides
        const dynamicTools = JSON.parse(JSON.stringify(TOOL_DEFINITIONS));
        const syntaxGuide = state ? this.getSyntaxGuide(state) : "";
        if (syntaxGuide) {
          const writeContentFileTool = dynamicTools.find(
            (t) => t.function?.name === "write_content_file",
          );
          if (
            writeContentFileTool &&
            writeContentFileTool.function.parameters?.properties?.syntax_guide
          ) {
            writeContentFileTool.function.parameters.properties.syntax_guide.description += ` Document-specific syntax conventions: ${syntaxGuide}`;
            writeContentFileTool.function.parameters.properties.syntax_guide.default =
              syntaxGuide;
          }
          const replaceSelectionTool = dynamicTools.find(
            (t) => t.function?.name === "replace_selection",
          );
          if (
            replaceSelectionTool &&
            replaceSelectionTool.function.parameters?.properties?.syntax_guide
          ) {
            replaceSelectionTool.function.parameters.properties.syntax_guide.description += ` Document-specific syntax conventions: ${syntaxGuide}`;
            replaceSelectionTool.function.parameters.properties.syntax_guide.default =
              syntaxGuide;
          }
        }

        const requestBody = {
          messages: payloadMessages,
          stream: true,
          tools: dynamicTools,
          tool_choice: "auto",
          surface: "editor",
        };

        if (DEBUG_AI) {
          console.groupCollapsed("🤖 AI Request Payload (Unfiltered)");
          console.log(JSON.parse(JSON.stringify(requestBody)));
          console.groupEnd();
        }

        const response = await fetch(`${apiBase}/ai/chat`, {
          method: "POST",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify(requestBody),
          signal: this.abortController.signal,
        });

        if (!response.ok) {
          const errJson = await response
            .json()
            .catch(() => ({ detail: "Unknown error" }));

          let errMsg = "";
          let errCode = null;
          if (errJson.detail && typeof errJson.detail === "object") {
            errMsg = errJson.detail.message || JSON.stringify(errJson.detail);
            errCode = errJson.detail.code || null;
          } else {
            errMsg = String(errJson.detail || response.statusText);
            if (errMsg.includes("image_input_not_supported")) {
              errCode = "image_input_not_supported";
            }
          }
          const error = new Error(errMsg);
          if (errCode) {
            error.code = errCode;
          }
          throw error;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        // Add the empty assistant message bubble to mutate in-place
        this.messages.push({ role: "assistant", content: "" });
        this.capMessages();
        this.saveMessages();
        const assistantIdx = this.messages.length - 1;
        this.$nextTick(() => this.scrollToBottom());

        this._pendingToolCalls = {};

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop(); // keep the last (potentially partial) line

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            if (!trimmed.startsWith("data:")) continue;

            const data = trimmed.slice(5).trim();
            if (data === "[DONE]") {
              if (DEBUG_AI) console.log("🤖 AI Stream: [DONE]");
              continue;
            }

            if (DEBUG_AI) {
              console.log("🤖 AI Stream Chunk (Raw):", data);
            }

            try {
              const json = JSON.parse(data);
              const delta = json.choices?.[0]?.delta;
              if (delta) {
                if (delta.content) {
                  this.messages[assistantIdx].content += delta.content;
                  this.$nextTick(() => this.scrollToBottom());
                }
                if (delta.tool_calls) {
                  for (const tc of delta.tool_calls) {
                    const idx = tc.index;
                    if (!this._pendingToolCalls[idx]) {
                      this._pendingToolCalls[idx] = {
                        id: tc.id || "",
                        type: "function",
                        function: { name: "", arguments: "" },
                      };
                    }
                    if (tc.id) this._pendingToolCalls[idx].id = tc.id;
                    if (tc.function?.name)
                      this._pendingToolCalls[idx].function.name +=
                        tc.function.name;
                    if (tc.function?.arguments)
                      this._pendingToolCalls[idx].function.arguments +=
                        tc.function.arguments;
                  }
                  this.$nextTick(() => this.scrollToBottom());
                }
              }
            } catch (e) {
              // ignore malformed lines
            }
          }
        }

        const toolCalls = Object.values(this._pendingToolCalls);
        if (toolCalls.length > 0) {
          // Populate the assistant message's tool_calls field
          this.messages[assistantIdx].tool_calls = toolCalls.map((tc) => ({
            id: tc.id,
            type: "function",
            function: {
              name: tc.function.name,
              arguments: tc.function.arguments,
            },
          }));
          this.saveMessages();

          // Execute each tool sequentially
          for (const tc of toolCalls) {
            let result;
            try {
              const args = tc.function.arguments
                ? JSON.parse(tc.function.arguments)
                : {};
              result = await this.executeTool(tc.function.name, args);
            } catch (e) {
              result = {
                error: `Failed to parse tool arguments: ${e.message}`,
              };
            }

            // Push tool response message
            this.messages.push({
              role: "tool",
              name: tc.function.name,
              tool_call_id: tc.id,
              content: JSON.stringify(result),
            });
            this.capMessages();
            this.saveMessages();
          }
          this._pendingToolCalls = {};
          this.$nextTick(() => this.scrollToBottom());

          // Recursive call — skip when a handoff is awaiting confirm or navigating away.
          if (!this.shouldPauseStreamForHandoff()) {
            await this.streamCompletion();
          }
        } else {
          // Fallback tool call parser: scan the assistant message content for tool call blocks
          const content = this.messages[assistantIdx].content || "";
          const regexes = [
            /```tool_call\s*([\s\S]*?)\s*```/g,
            /```json\s*([\s\S]*?)\s*```/g,
          ];
          const parsedToolCalls = [];

          for (const regex of regexes) {
            const matches = [...content.matchAll(regex)];
            for (const match of matches) {
              try {
                const parsed = JSON.parse(match[1]);
                let name = parsed.name;
                let args = parsed.arguments || parsed;

                if (!name) {
                  // Heuristic guessing of tool name based on parameter keys
                  if (args.query) {
                    name = "search_content";
                  } else if (args.slug && (args.body || args.frontmatter)) {
                    name = "write_content_file";
                  } else if (args.slug) {
                    name = "read_page_content";
                  } else if (args.filename && args.content_base64) {
                    name = "write_media_file";
                  } else if (args.collection_name) {
                    name = "list_collection_entries";
                  }
                }

                if (name) {
                  parsedToolCalls.push({
                    id:
                      "call_text_" +
                      Date.now() +
                      "_" +
                      Math.random().toString(36).substr(2, 5),
                    type: "function",
                    function: {
                      name: name,
                      arguments: JSON.stringify(args),
                    },
                  });
                }
              } catch (err) {
                // Ignore parse errors for non-tool JSON blocks
              }
            }
          }

          // Fallback: match raw curly brace structures if no fenced code blocks matched
          if (parsedToolCalls.length === 0) {
            const regexRawJson = /\{[\s\S]*?\}/g;
            const matchesRaw = content.match(regexRawJson) || [];
            for (const textJson of matchesRaw) {
              try {
                const parsed = JSON.parse(textJson);
                let name = parsed.name;
                let args = parsed.arguments || parsed;

                if (!name) {
                  // Heuristic guessing of tool name based on parameter keys
                  if (args.query) {
                    name = "search_content";
                  } else if (args.slug && (args.body || args.frontmatter)) {
                    name = "write_content_file";
                  } else if (args.slug) {
                    name = "read_page_content";
                  } else if (args.filename && args.content_base64) {
                    name = "write_media_file";
                  } else if (args.collection_name) {
                    name = "list_collection_entries";
                  }
                }

                if (name) {
                  parsedToolCalls.push({
                    id:
                      "call_text_" +
                      Date.now() +
                      "_" +
                      Math.random().toString(36).substr(2, 5),
                    type: "function",
                    function: {
                      name: name,
                      arguments: JSON.stringify(args),
                    },
                  });
                }
              } catch (err) {
                // Ignore parse errors
              }
            }
          }

          if (parsedToolCalls.length > 0) {
            // Populate the assistant message's tool_calls field
            this.messages[assistantIdx].tool_calls = parsedToolCalls;
            this.saveMessages();

            // Execute each tool sequentially
            for (const tc of parsedToolCalls) {
              let result;
              try {
                const args = JSON.parse(tc.function.arguments);
                result = await this.executeTool(tc.function.name, args);
              } catch (e) {
                result = {
                  error: `Failed to execute fallback tool: ${e.message}`,
                };
              }

              // Push tool response message
              this.messages.push({
                role: "tool",
                name: tc.function.name,
                tool_call_id: tc.id,
                content: JSON.stringify(result),
              });
              this.capMessages();
              this.saveMessages();
            }
            this.$nextTick(() => this.scrollToBottom());

            // Recursive call — skip when a handoff is awaiting confirm or navigating away.
            if (!this.shouldPauseStreamForHandoff()) {
              await this.streamCompletion();
            }
          } else {
            // If no tool calls were made and the content is empty, show a fallback message
            if (!this.messages[assistantIdx].content?.trim()) {
              this.messages[assistantIdx].content =
                "[The AI provider returned an empty response or timed out. Please try again]";
              this.saveMessages();
            }
          }
        }
      } catch (e) {
        if (e.name === "AbortError" || this.isHandoffNavNoise(e)) {
          console.log("AI Generation stream aborted.");
        } else {
          console.error(e);
          this.showToast(`AI Proxy Error: ${e.message}`, "error");

          let errorType = null;
          if (
            e.code === "image_input_not_supported" ||
            e.message.includes("image_input_not_supported") ||
            e.message.includes("does not support image inputs")
          ) {
            errorType = "image_input_not_supported";
          }

          this.messages.push({
            role: "assistant",
            content: `*Error during generation:* ${e.message}`,
            errorType: errorType,
          });
          this.capMessages();
          this.saveMessages();
        }
      } finally {
        this.streaming = false;
        this._stopStreamingWordCycle();
        this.abortController = null;
        // NOTE: attachedImages are intentionally NOT cleared here since the LLM may need
        // to reference them later (e.g. 'now add that image to the post'). They are only
        // cleared on newConversation() or when the user removes them via the ✕ button.
        this.saveMessages();
        if (!this._handoffNavigating) {
          this.focusPrompt();
        }
        if (isOuter) {
          this._handoffTurnActive = false;
          this._handoffForThisTurn = null;
        }
      }
    },

    fillPrompt(action) {
      const prompts = {
        seo: "Analyze the SEO of this content and suggest specific improvements to the title, meta description, headings, and keyword usage.",
        rewrite:
          "Rewrite the selected content to be more engaging and readable while preserving the key information. Return ONLY the rewritten text as raw markdown. Do not include any introduction, explanations, key improvements list, or conversational filler.",
        meta: "Write an optimized 150-160 character meta description for this content. Return ONLY the description text, nothing else.",
        expand:
          "Expand the selected content with more detail, supporting information, and examples. Return ONLY the expanded markdown content, nothing else.",
        links:
          "Suggest relevant internal links or Nutshell ([expand]/[embed]) options for the current text focus. Use suggest_internal_links, then for Nutshells call insert_expand_embed (and list_page_headings if a section is needed). For normal links use [text](slug).",
        generate_image:
          "Generate a high-quality contextual image for this post. Analyze the content to construct a detailed generation prompt, save the image with a clean filename, and return the image URL so it can be added to the post.",
        attach_images:
          "Process and save all currently attached/uploaded images to the post's media library (using the attach_image_to_post tool) and insert them at logical places in the post body.",
        git_commit:
          "Review all the recent changes to the repository, write a descriptive and concise commit message, and stage, commit, and push the changes to the remote. Run a dry run first to show the changes, then proceed.",
        quality_check:
          "Evaluate this post against the quality checklist. Call the review_post tool with the current document slug and provide a detailed scorecard with specific improvement suggestions.",
      };
      this.prompt = prompts[action] || "";
      this.$nextTick(() => {
        const ta = document.getElementById("ai-prompt-textarea");
        if (ta) {
          ta.focus();
          ta.setSelectionRange(ta.value.length, ta.value.length);
          this.autoGrow(ta);
        }
      });
    },

    autoGrow(el) {
      if (!el) return;
      el.style.height = "auto";
      // ~15 lines at text-xs/leading-relaxed; CSS max-h-[320px] mirrors this.
      el.style.height = Math.min(el.scrollHeight, 320) + "px";
    },

    handleFileSelect(e) {
      const files = e.target.files;
      if (!files) return;
      this.addFiles(files);
      e.target.value = ""; // Reset file input
    },

    removeAttachedImage(index) {
      this.attachedImages.splice(index, 1);
    },

    removeImageFromChatAndPending(msg, imgIdx) {
      const img = msg.attachedImages[imgIdx];
      if (!img) return;
      msg.attachedImages.splice(imgIdx, 1);
      const pendingIdx = this.attachedImages.findIndex(
        (i) => i.name === img.name,
      );
      if (pendingIdx !== -1) {
        this.attachedImages.splice(pendingIdx, 1);
      }
      this.saveMessages();
    },

    clearAttachedImages() {
      this.attachedImages = [];
    },

    retryWithoutImages() {
      if (
        this.messages.length > 0 &&
        this.messages[this.messages.length - 1].role === "assistant"
      ) {
        this.messages.pop();
      }

      let lastUserMsgIdx = -1;
      for (let i = this.messages.length - 1; i >= 0; i--) {
        if (this.messages[i].role === "user") {
          lastUserMsgIdx = i;
          break;
        }
      }

      if (lastUserMsgIdx !== -1) {
        const userMsg = this.messages[lastUserMsgIdx];
        if (Array.isArray(userMsg.content)) {
          const textPart = userMsg.content.find((p) => p.type === "text");
          let text = textPart ? textPart.text : "";
          text = text.replace(
            /<attached_images>[\s\S]*?<\/attached_images>\n*/g,
            "",
          );
          userMsg.content = text;
        } else if (typeof userMsg.content === "string") {
          userMsg.content = userMsg.content.replace(
            /<attached_images>[\s\S]*?<\/attached_images>\n*/g,
            "",
          );
        }
        if (userMsg.displayContent) {
          userMsg.displayContent = userMsg.displayContent.replace(
            /🖼️ \*\*Image\(s\):\*\*.*?\n\n/g,
            "",
          );
        }
      }

      this.attachedImages = [];
      this.saveMessages();
      this.$nextTick(() => {
        this.scrollToBottom();
      });
      this.streamCompletion();
    },

    handleFileDrop(e) {
      const files = e.dataTransfer?.files;
      if (files && files.length > 0) {
        this.addFiles(files);
      }
    },

    handlePaste(e) {
      const items = e.clipboardData?.items;
      if (!items) return;

      const imageFiles = [];
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) imageFiles.push(file);
        }
      }

      if (imageFiles.length > 0) {
        e.preventDefault();
        this.addFiles(imageFiles);
      }
    },

    addFiles(files) {
      const IMAGE_TYPES = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/gif",
        "image/webp",
      ];
      const TEXT_EXTS = ["txt", "md"];
      const IMAGE_EXTS = ["png", "jpg", "jpeg", "gif", "webp"];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const ext = file.name.split(".").pop().toLowerCase();
        const isImage =
          IMAGE_TYPES.includes(file.type) || IMAGE_EXTS.includes(ext);
        const isText = TEXT_EXTS.includes(ext) && !isImage;

        if (!isText && !isImage) {
          this.showToast(
            `Unsupported file type: ${file.name}. Use .txt, .md, or images (.png, .jpg, .gif, .webp).`,
            "error",
          );
          continue;
        }

        if (isImage) {
          const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // 10 MB
          if (file.size > MAX_IMAGE_BYTES) {
            this.showToast(
              `Image ${file.name} is too large. Max allowed size is 10MB.`,
              "error",
            );
            continue;
          }
          if (this.attachedImages.some((f) => f.name === file.name)) {
            this.showToast(`Image ${file.name} is already attached.`, "error");
            continue;
          }

          // Immediately push entry with encoding: true
          const initialEntry = {
            name: file.name,
            dataUrl: null,
            type: file.type,
            size: file.size,
            encoding: true,
            width: null,
            height: null,
            estimatedTokens: null,
          };
          this.attachedImages.push(initialEntry);

          const reader = new FileReader();
          reader.onload = (event) => {
            const dataUrl = event.target.result;
            const imgEl = new Image();
            imgEl.onload = () => {
              const entry = this.attachedImages.find(
                (f) => f.name === file.name && f.encoding,
              );
              if (entry) {
                entry.dataUrl = dataUrl;
                entry.width = imgEl.naturalWidth;
                entry.height = imgEl.naturalHeight;
                const maxDim = Math.max(
                  imgEl.naturalWidth,
                  imgEl.naturalHeight,
                );
                entry.estimatedTokens = maxDim > 512 ? 1100 : 85;
                entry.encoding = false;
              }
            };
            imgEl.onerror = () => {
              const entry = this.attachedImages.find(
                (f) => f.name === file.name && f.encoding,
              );
              if (entry) {
                entry.dataUrl = dataUrl;
                entry.encoding = false;
              }
            };
            imgEl.src = dataUrl;
          };
          reader.onerror = () => {
            this.showToast(`Error reading image: ${file.name}`, "error");
            const idx = this.attachedImages.findIndex(
              (f) => f.name === file.name && f.encoding,
            );
            if (idx !== -1) {
              this.attachedImages.splice(idx, 1);
            }
          };
          reader.readAsDataURL(file);
        } else {
          const reader = new FileReader();
          reader.onload = (event) => {
            const content = event.target.result;
            if (content.length > 50000) {
              this.showToast(
                `File ${file.name} is too large. Max allowed size is 50KB.`,
                "error",
              );
              return;
            }
            if (this.attachedFiles.some((f) => f.name === file.name)) {
              this.showToast(`File ${file.name} is already attached.`, "error");
              return;
            }
            this.attachedFiles.push({
              name: file.name,
              content: content,
            });
          };
          reader.onerror = () => {
            this.showToast(`Error reading file: ${file.name}`, "error");
          };
          reader.readAsText(file);
        }
      }
    },

    removeAttachedFile(index) {
      this.attachedFiles.splice(index, 1);
    },

    handleEnterKey(e) {
      // Shift+Enter inserts a newline; bare Enter sends.
      if (e.shiftKey) return;
      e.preventDefault();
      if (
        !this.streaming &&
        (this.prompt.trim() ||
          this.attachedFiles.length > 0 ||
          this.attachedImages.length > 0)
      )
        this.sendPrompt();
    },

    applyToEditor(content) {
      const editor = window.getPenEditor ? window.getPenEditor() : null;
      if (!editor) {
        this.showToast("Open a document first.", "error");
        return;
      }
      editor.replaceSelection(content);
      editor.focus();
      this.showToast("Content applied to active editor selection.");
    },

    copyToClipboard(content, index) {
      if (!navigator.clipboard) {
        this.showToast(
          "Clipboard access not supported in this browser.",
          "error",
        );
        return;
      }
      navigator.clipboard
        .writeText(content)
        .then(() => {
          this.showToast("Copied content to clipboard.");
          if (index !== undefined) {
            this.copiedMessageIndex = index;
            setTimeout(() => {
              if (this.copiedMessageIndex === index) {
                this.copiedMessageIndex = null;
              }
            }, 2000);
          }
        })
        .catch((err) =>
          this.showToast("Failed to copy to clipboard.", "error"),
        );
    },

    scrollToBottom() {
      const container = document.getElementById("ai-chat-messages-container");
      if (container) {
        // Defer to next frame so newly-appended DOM nodes have measurable height.
        requestAnimationFrame(() => {
          container.scrollTop = container.scrollHeight;
        });
      }
    },

    focusPrompt() {
      this.$nextTick(() => {
        this.scrollToBottom();
        requestAnimationFrame(() => {
          const ta = document.getElementById("ai-prompt-textarea");
          if (ta && !ta.disabled) ta.focus();
        });
      });
    },

    saveMessages() {
      try {
        sessionStorage.setItem(
          this.chatStorageKey("pen_messages"),
          JSON.stringify(this.messages),
        );
      } catch (e) {
        console.warn("Failed to save messages to sessionStorage", e);
      }
    },

    saveSessionContext() {
      try {
        sessionStorage.setItem(
          this.chatStorageKey("pen_session_context"),
          JSON.stringify(this.session_context),
        );
      } catch (e) {
        console.warn("Failed to save session context to sessionStorage", e);
      }
    },

    capMessages() {
      const LIMIT = 50;
      if (this.messages.length > LIMIT) {
        this.messages = this.messages.slice(-LIMIT);
      }
    },

    addSessionContext(action, summary, accepted = true, id = null) {
      if (!this.session_context) {
        this.session_context = [];
      }
      this.session_context.push({
        id:
          id ||
          "tx_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6),
        action: action,
        accepted: accepted,
        timestamp: Date.now(),
        summary: summary,
      });
      if (this.session_context.length > 10) {
        this.session_context.shift();
      }
      this.saveSessionContext();
    },

    newConversation() {
      this.messages = [];
      this.session_context = [];
      this.attachedFiles = [];
      this.attachedImages = [];
      this.saveMessages();
      this.saveSessionContext();
      this.showToast("New conversation started.");
    },

    showTokenWarningModal(tokenEstimate) {
      this.tokenWarningCount = tokenEstimate;
      this.tokenWarningModalOpen = true;
      return new Promise((resolve) => {
        this.tokenWarningResolve = resolve;
      });
    },

    confirmTokenWarning(value) {
      this.tokenWarningModalOpen = false;
      if (this.tokenWarningResolve) {
        this.tokenWarningResolve(value);
        this.tokenWarningResolve = null;
      }
    },

    pushToUndoStack(entry) {
      if (this.undoStack.length >= 20) {
        this.undoStack.shift();
      }
      this.undoStack.push(entry);
      try {
        sessionStorage.setItem(
          this.chatStorageKey("pen_undo_stack"),
          JSON.stringify(this.undoStack),
        );
      } catch (e) {
        console.warn("Failed to save undo stack to sessionStorage", e);
      }
    },

    undo() {
      if (this.undoStack.length === 0) {
        this.showToast("Nothing to undo", "info");
        return;
      }

      const entry = this.undoStack.pop();
      try {
        sessionStorage.setItem(
          this.chatStorageKey("pen_undo_stack"),
          JSON.stringify(this.undoStack),
        );
      } catch (e) {}

      if (entry.is_structural) {
        this.showToast("Undoing structural refactoring...", "info");
        this.restoreStructuralState(entry.slug, entry.previousState)
          .then(() => {
            this.showToast("Structural refactoring undone.", "success");
          })
          .catch((e) => {
            this.showToast(
              `Failed to undo structural refactoring: ${e.message}`,
              "error",
            );
          });
        return;
      }

      if (entry.id && this.session_context) {
        const contextEntry = this.session_context.find(
          (item) => item.id === entry.id,
        );
        if (contextEntry) {
          contextEntry.accepted = false;
          this.saveSessionContext();
        }
      }

      const { field, previousValue } = entry;
      const parentData = window.Alpine && Alpine.$data(document.body);

      const frontmatterFields = [
        "title",
        "status",
        "category",
        "deck",
        "summary",
        "faqs",
        "author",
        "date",
        "hero_image",
        "hero_title",
        "trumpet",
        "domain",
      ];

      if (
        frontmatterFields.includes(field) ||
        (parentData && parentData.form && parentData.form[field] !== undefined)
      ) {
        if (parentData && parentData.form) {
          parentData.form[field] = previousValue;
          this.showToast(`Restored metadata field: ${field}`);
        }
      } else {
        const editor = window.getPenEditor?.(field);
        if (editor) {
          editor.setValue(previousValue);
          editor.focus();
          this.showToast(`Restored editor text: ${field}`);
        } else {
          this.showToast(`Could not restore state for: ${field}`, "error");
        }
      }
    },

    async attach_image_to_post(args) {
      const { image_index, filename, caption, alt_text } = args;

      if (typeof image_index !== "number" || image_index < 0) {
        return { error: "Invalid image_index. Must be a non-negative number." };
      }
      if (image_index >= (this.attachedImages || []).length) {
        return {
          error: `image_index ${image_index} is out of range. The user has ${this.attachedImages?.length || 0} attached image(s). Note: this tool is for user-uploaded attachments only. If you used generate_media to create an AI image, it is already in the media gallery — use its relative_path directly in the [image src="..."] shortcode.`,
        };
      }
      if (!filename || typeof filename !== "string") {
        return {
          error: "A filename is required (e.g. 'images/content/photo.jpg').",
        };
      }

      const img = this.attachedImages[image_index];

      // Strip the data URL prefix to get raw base64
      // data:image/jpeg;base64,/9j/4AAQ... → /9j/4AAQ...
      const dataUrl = img.dataUrl;
      const base64Match = dataUrl.match(/^data:[^;]+;base64,(.+)$/);
      if (!base64Match) {
        return { error: "Could not decode the image data." };
      }
      const content_base64 = base64Match[1];

      // Reuse the existing write_media_file MCP tool on the server
      const mcpArgs = { filename, content_base64 };
      try {
        const result = await this.executeMcpToolOnServer(
          "write_media_file",
          mcpArgs,
        );
        if (result && !result.error) {
          // Refresh the media gallery in the wizard sidebar
          const wizard = window.Alpine && Alpine.$data(document.body);
          if (wizard && typeof wizard.loadAssets === "function") {
            await wizard.loadAssets();
          }
          this.showToast(`Image "${img.name}" written to media gallery.`);
          // Remove from attachedImages — it's in the gallery now.
          this.attachedImages.splice(image_index, 1);
        }
        return result;
      } catch (e) {
        return { error: `Failed to write image to media: ${e.message}` };
      }
    },

    async replace_selection(args) {
      const editor = window.getPenEditor?.();
      if (!editor) return { error: "No active editor" };

      // Fail loudly with an actionable hint when there is no selection.
      // Otherwise the tool silently no-ops and the model believes the
      // edit landed (the symptom from the smoketest). Returning an explicit
      // error here lets the agent loop self-correct on the next turn by
      // falling back to write_content_file.
      const view = editor.getView?.();
      let hasSelection = view && !view.state.selection.main.empty;

      // Fallback/Force restore: Ensure target selection matches the original range at submission time
      if (this._lastSelectionRange) {
        try {
          const editorName = this._lastSelectionRange.editorName;
          const targetEditor = window.getPenEditor?.(editorName);
          if (targetEditor) {
            const targetView = targetEditor.getView?.();
            if (targetView) {
              const docLen = targetView.state.doc.length;
              const { from, to } = this._lastSelectionRange;
              if (from <= docLen && to <= docLen) {
                targetView.dispatch({
                  selection: { anchor: from, head: to },
                  scrollIntoView: true,
                });
                hasSelection = true;
              }
            }
          }
        } catch (err) {
          console.warn("Failed to restore selection from fallback range:", err);
        }
      }

      if (!hasSelection) {
        return {
          error:
            "No active text selection in the editor. replace_selection requires a selection. For edits with no selection, call write_content_file with the slug and the FULL updated body — the current body is already in your system prompt under 'Document Body' / 'Main Body (index.md)'; do not call read_page_content or get_document_outline first.",
        };
      }

      const activePartial =
        (window.Alpine && Alpine.$data(document.body)?.activePartial) || "main";
      const field = activePartial === "main" ? "body" : activePartial;
      const previousValue = editor.getValue();

      const txId =
        "tx_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6);
      this.pushToUndoStack({
        id: txId,
        field: field,
        previousValue: previousValue,
        timestamp: Date.now(),
      });

      editor.replaceSelection(args.new_text);
      editor.focus();
      this._lastSelectionRange = null; // Clear range after replacement

      const snippet =
        args.new_text.length > 30
          ? args.new_text.substring(0, 30) + "..."
          : args.new_text;
      this.addSessionContext(
        "replace_selection",
        `Replaced selected text with "${snippet}"`,
        true,
        txId,
      );

      const parentData = window.Alpine && Alpine.$data(document.body);
      if (parentData && typeof parentData.save === "function") {
        const saveRes = await parentData.save({ silent: true });
        if (saveRes && !saveRes.success) {
          return { error: saveRes.error };
        }
      }

      return { success: true };
    },

    async insert_at_cursor(args) {
      const editor = window.getPenEditor?.();
      if (!editor) return { error: "No active editor" };

      const activePartial =
        (window.Alpine && Alpine.$data(document.body)?.activePartial) || "main";
      const field = activePartial === "main" ? "body" : activePartial;
      const previousValue = editor.getValue();

      const txId =
        "tx_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6);
      this.pushToUndoStack({
        id: txId,
        field: field,
        previousValue: previousValue,
        timestamp: Date.now(),
      });

      editor.replaceSelection(args.content);
      editor.focus();

      const snippet =
        args.content.length > 30
          ? args.content.substring(0, 30) + "..."
          : args.content;
      this.addSessionContext(
        "insert_at_cursor",
        `Inserted text "${snippet}" at cursor`,
        true,
        txId,
      );

      const parentData = window.Alpine && Alpine.$data(document.body);
      if (parentData && typeof parentData.save === "function") {
        const saveRes = await parentData.save({ silent: true });
        if (saveRes && !saveRes.success) {
          return { error: saveRes.error };
        }
      }

      return { success: true };
    },

    async update_frontmatter_field(args) {
      const parentData = window.Alpine && Alpine.$data(document.body);
      if (!parentData || !parentData.form) {
        return { error: "Failed to access frontmatter form data" };
      }

      const previousValue =
        parentData.form[args.key] !== undefined
          ? parentData.form[args.key]
          : null;

      const txId =
        "tx_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6);
      this.pushToUndoStack({
        id: txId,
        field: args.key,
        previousValue: previousValue,
        timestamp: Date.now(),
      });

      let val = args.value;
      if (args.key === "faqs") {
        if (typeof val === "string") {
          const raw = val.trim();
          if (!raw) {
            val = [];
          } else {
            try {
              val = JSON.parse(raw);
            } catch (_) {
              return { error: "faqs must be a JSON array of {q, a} objects." };
            }
          }
        }
        if (!Array.isArray(val)) {
          return { error: "faqs must be an array of {q, a} objects." };
        }
        val = val.map((item) => ({
          q: String(item && item.q != null ? item.q : ""),
          a: String(item && item.a != null ? item.a : ""),
        }));
      } else if (args.key === "page" || args.key === "needs_review" || args.key === "published" || args.key === "pinned" || args.key === "noindex") {
        if (typeof val === "string") {
          val = (val.toLowerCase() === "true");
        } else {
          val = !!val;
        }
      }
      parentData.form[args.key] = val;

      this.addSessionContext(
        "update_frontmatter_field",
        `Updated frontmatter field "${args.key}" to "${args.value}"`,
        true,
        txId,
      );

      if (parentData && typeof parentData.save === "function") {
        const saveRes = await parentData.save({ silent: true });
        if (saveRes && !saveRes.success) {
          return { error: saveRes.error };
        }
      }

      const result = { success: true, key: args.key, value: args.value };

      // Soft-check image frontmatter fields against the media library.
      if (
        (args.key === "hero_image" || args.key === "main_image") &&
        typeof val === "string" &&
        val.trim()
      ) {
        const path = val.trim();
        if (
          path.startsWith("http://") ||
          path.startsWith("https://")
        ) {
          // External URLs are allowed without library check.
        } else if (
          path.includes("/api/assets/raw/") ||
          path.startsWith("/api/assets/")
        ) {
          result.media_path_warnings = [
            `Media path looks like a public_url API path ('${path}'). ` +
              "Use the site-relative relative_path from generate_media / list_media " +
              "in hero_image / main_image.",
          ];
        } else {
          try {
            const media = await this.executeMcpToolOnServer("list_media", {});
            const files = Array.isArray(media) ? media : [];
            const known = new Set(
              files
                .map((f) => f.filename || f.relative_path || "")
                .filter(Boolean),
            );
            const normalized = path.replace(/^\/+/, "");
            if (!known.has(normalized) && !known.has(path)) {
              result.media_path_warnings = [
                `Media path not found in site library: '${path}'. ` +
                  "Use relative_path from generate_media / list_media.",
              ];
            }
          } catch (e) {
            // Soft check only — never fail the frontmatter update.
            console.warn(
              "[update_frontmatter_field] media path soft-check failed:",
              e,
            );
          }
        }
      }

      return result;
    },

    async get_document_outline() {
      let segments = [];
      const strip = window.fromEditorContentUrls;

      // Prefer per-editor getMarkdownState().body (strips frontmatter cleanly)
      const mainEditor = window.getPenEditor?.("main");
      if (mainEditor?.getMarkdownState) {
        segments.push(mainEditor.getMarkdownState().body || "");
      } else if (mainEditor?.getValue) {
        segments.push(mainEditor.getValue());
      }

      // Also pull composite partials if present (already stripped by getPenDocumentContext)
      const docContext = window.getPenDocumentContext?.();
      if (docContext && Object.keys(docContext.partials).length > 0) {
        Object.values(docContext.partials).forEach((val) => {
          if (val) segments.push(val);
        });
      }

      let doc = segments.join("\n\n").replace(/\r/g, "");
      if (typeof strip === "function") doc = strip(doc);

      if (!doc.trim()) {
        console.warn(
          "[get_document_outline] No document content found. Editor may not be loaded yet.",
        );
        return { headings: [] };
      }

      const headings = [];
      for (const line of doc.split("\n")) {
        const match = line.match(/^(#{1,6})\s+(.*)$/);
        if (match) {
          headings.push({ level: match[1].length, text: match[2].trim() });
        }
      }
      return { headings };
    },

    async get_selection_context() {
      const editor = window.getPenEditor?.();
      if (!editor) return { error: "No active editor" };

      const doc = editor.getValue();
      const view = editor.getView?.();
      if (!view) return { error: "Cannot access editor view" };

      const range = view.state.selection.main;
      const from = range.from;
      const to = range.to;
      const selection = doc.slice(from, to);

      const beforeText = doc.slice(0, from);
      const afterText = doc.slice(to);

      const beforeParagraphs = beforeText.split(/\n\n+/);
      const afterParagraphs = afterText.split(/\n\n+/);

      const before = beforeParagraphs.slice(-2).join("\n\n");
      const after = afterParagraphs.slice(0, 2).join("\n\n");

      const strip = window.fromEditorContentUrls;
      if (typeof strip === "function") {
        return {
          selection: strip(selection),
          before: strip(before),
          after: strip(after),
        };
      }
      return { selection, before, after };
    },

    async suggest_internal_links(args) {
      let query = args.query;
      if (!query) {
        const editor = window.getPenEditor?.();
        if (editor) {
          const doc = editor.getValue();
          const view = editor.getView?.();
          if (view) {
            const range = view.state.selection.main;
            if (!range.empty) {
              query = doc.slice(range.from, range.to);
            } else {
              const pos = range.from;
              const beforeText = doc.slice(0, pos);
              const afterText = doc.slice(pos);

              const beforeLines = beforeText.split("\n");
              const afterLines = afterText.split("\n");

              const currentLine =
                (beforeLines[beforeLines.length - 1] || "") +
                (afterLines[0] || "");
              query = currentLine.trim();
            }
          }
        }
      }

      if (!query || query.length < 3) {
        const parentData = window.Alpine && Alpine.$data(document.body);
        query =
          (parentData && parentData.form && parentData.form.hero_title) ||
          (parentData && parentData.form && parentData.form.name) ||
          (parentData && parentData.form && parentData.form.title) ||
          new URLSearchParams(window.location.search).get("id") ||
          "";
      }

      query = String(query || "")
        .replace(/[#*`_\[\]()]/g, " ")
        .trim();

      const usage_hint =
        "For Nutshells call insert_expand_embed; for normal links use markdown_link / [text](slug).";

      const store = window.Alpine && Alpine.store("app");
      if (!store || typeof store.getPublishedLinkCatalog !== "function") {
        return { error: "Published link catalog unavailable." };
      }

      // Prefer shorter catalog tokens (typeahead-style) while keeping full query for FTS.
      const words = query.split(/\s+/).filter((w) => w.length > 2);
      const catalogQuery = words[0] || query;
      const searchTerms = words.slice(0, 4).join(" ") || query;

      try {
        const bySlug = new Map();
        const catalog = await store.getPublishedLinkCatalog(catalogQuery, 12);
        for (const row of catalog) {
          bySlug.set(row.slug, { ...row });
        }

        // If thin, try each significant word against the catalog.
        if (bySlug.size < 3 && words.length > 1) {
          for (const w of words.slice(0, 4)) {
            const more = await store.getPublishedLinkCatalog(w, 12);
            for (const row of more) {
              if (!bySlug.has(row.slug)) bySlug.set(row.slug, { ...row });
            }
            if (bySlug.size >= 8) break;
          }
        }

        // Optional FTS merge when catalog still thin — keep only live-published slugs.
        if (searchTerms && bySlug.size < 3) {
          const allLive = await store.getPublishedLinkCatalog("", 10000);
          const liveBySlug = new Map(allLive.map((r) => [r.slug, r]));
          try {
            const searchResult = await this.executeTool("search_content", {
              query: searchTerms,
              limit: 8,
            });
            const hits = Array.isArray(searchResult)
              ? searchResult
              : searchResult?.results || searchResult?.items || [];
            for (const hit of hits) {
              const hitSlug = String(hit.slug || hit.id || "").trim();
              if (!hitSlug || !liveBySlug.has(hitSlug) || bySlug.has(hitSlug))
                continue;
              const base = liveBySlug.get(hitSlug);
              bySlug.set(hitSlug, {
                ...base,
                excerpt: hit.excerpt || null,
              });
              if (bySlug.size >= 8) break;
            }
          } catch (_) {
            /* FTS optional */
          }
        }

        const results = [...bySlug.values()].slice(0, 8);
        if (!results.length && !query) {
          return {
            error:
              "Could not determine search query from current editor context.",
          };
        }
        return {
          query_used: searchTerms || catalogQuery || query,
          results,
          usage_hint,
        };
      } catch (e) {
        return { error: `Failed to suggest links: ${e.message}` };
      }
    },

    _escapeShortcodeAttr(value) {
      return String(value ?? "")
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"');
    },

    _buildExpandEmbedShortcode({ mode, slug, text, heading, source }) {
      const m = mode === "embed" ? "embed" : "expand";
      const parts = [`${m} slug="${this._escapeShortcodeAttr(slug)}"`];
      if (text != null && String(text).trim() !== "") {
        parts.push(`text="${this._escapeShortcodeAttr(String(text).trim())}"`);
      }
      const src =
        source != null && String(source).trim() !== ""
          ? String(source).trim()
          : null;
      if (src) {
        parts.push(`source="${this._escapeShortcodeAttr(src)}"`);
      } else if (heading != null && String(heading).trim() !== "") {
        parts.push(
          `heading="${this._escapeShortcodeAttr(String(heading).trim())}"`,
        );
      }
      return `[${parts.join(" ")}]`;
    },

    _parseExpandEmbedRefs(text) {
      const refs = [];
      const re = /\[(expand|embed)\s*([^\]]*)\]/gi;
      let m;
      while ((m = re.exec(text || "")) !== null) {
        const mode = m[1].toLowerCase();
        const attr = m[2] || "";
        let slug = "";
        let heading = null;
        const slugMatch = attr.match(
          /(?:^|\s)slug\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s\]]+))/i,
        );
        const defMatch = attr.match(
          /^\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s\]]+))/,
        );
        const headMatch = attr.match(
          /heading\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s\]]+))/i,
        );
        if (slugMatch) slug = slugMatch[1] || slugMatch[2] || slugMatch[3] || "";
        else if (defMatch)
          slug = defMatch[1] || defMatch[2] || defMatch[3] || "";
        if (headMatch)
          heading = headMatch[1] || headMatch[2] || headMatch[3] || null;
        if (slug.includes("#")) {
          const parts = slug.split("#");
          slug = parts[0];
          if (!heading) heading = parts.slice(1).join("#") || null;
        }
        refs.push({ mode, slug: String(slug || "").trim(), heading });
      }
      return refs;
    },

    async insert_expand_embed(args) {
      const mode = args.mode === "embed" ? "embed" : "expand";
      const slug = String(args.slug || "").trim();
      if (!slug) {
        return { error: "slug is required." };
      }

      const store = window.Alpine && Alpine.store("app");
      if (!store || typeof store.getPublishedLinkCatalog !== "function") {
        return { error: "Published link catalog unavailable." };
      }

      const catalog = await store.getPublishedLinkCatalog("", 10000);
      const match = catalog.find((r) => r.slug === slug);
      if (!match) {
        return {
          error: `Slug "${slug}" not found or not live-published. Call suggest_internal_links and pick a published target.`,
        };
      }

      const editor = window.getPenEditor?.();
      if (!editor) return { error: "No active editor" };

      const view = editor.getView?.();
      const hasSelection = view && !view.state.selection.main.empty;
      let placement = args.placement;
      if (placement !== "selection" && placement !== "cursor") {
        placement = hasSelection ? "selection" : "cursor";
      }

      let text = args.text;
      if (text == null || String(text).trim() === "") {
        if (hasSelection) {
          const doc = editor.getValue();
          const range = view.state.selection.main;
          text = doc.slice(range.from, range.to).trim();
        }
        if (!text) text = match.suggested_text || match.title || slug;
      }

      const heading =
        args.heading != null && String(args.heading).trim() !== ""
          ? String(args.heading).trim()
          : null;
      const source =
        args.source != null && String(args.source).trim() !== ""
          ? String(args.source).trim()
          : null;

      if (source && heading) {
        return {
          error:
            'Do not set both source and heading. Use source="summary" or source="deck" for a nutshell, or heading= for a section slice.',
        };
      }
      if (source && source !== "deck" && source !== "summary") {
        return {
          error: `Unsupported source "${source}". Only source="summary" or source="deck" is allowed.`,
        };
      }

      const shortcode = this._buildExpandEmbedShortcode({
        mode,
        slug,
        text: mode === "expand" || text ? text : null,
        heading,
        source,
      });

      if (placement === "selection") {
        if (!hasSelection && !this._lastSelectionRange) {
          return {
            error:
              "placement=selection but there is no active selection. Use placement=cursor or select text first.",
          };
        }
        const result = await this.replace_selection({ new_text: shortcode });
        if (result && result.error) return result;
        return { ok: true, shortcode, placement: "selection", slug, mode, source };
      }

      const result = await this.insert_at_cursor({ content: shortcode });
      if (result && result.error) return result;
      return { ok: true, shortcode, placement: "cursor", slug, mode, source };
    },

    async check_expand_refs(args) {
      let text = args.markdown;
      if (text == null || text === "") {
        const blobs = [];
        const mainEditor = window.getPenEditor?.("main");
        if (mainEditor?.getMarkdownState) {
          blobs.push(mainEditor.getMarkdownState().body || "");
        } else if (mainEditor?.getValue) {
          blobs.push(mainEditor.getValue() || "");
        } else {
          const ed = window.getPenEditor?.();
          if (ed?.getValue) blobs.push(ed.getValue() || "");
        }
        const docContext = window.getPenDocumentContext?.();
        if (docContext?.partials) {
          Object.values(docContext.partials).forEach((v) => {
            if (v) blobs.push(v);
          });
        }
        text = blobs.join("\n");
      }

      const refs = this._parseExpandEmbedRefs(text);
      if (!refs.length) {
        return { ok: true, broken: [], checked: 0 };
      }

      const store = window.Alpine && Alpine.store("app");
      if (!store || typeof store.getPublishedLinkCatalog !== "function") {
        return { error: "Published link catalog unavailable." };
      }
      const catalog = await store.getPublishedLinkCatalog("", 10000);
      const published = new Set(catalog.map((r) => r.slug));

      const broken = [];
      for (const ref of refs) {
        if (!ref.slug) {
          broken.push({
            slug: "",
            heading: ref.heading,
            mode: ref.mode,
            reason: "missing_slug",
          });
          continue;
        }
        if (!published.has(ref.slug)) {
          broken.push({
            slug: ref.slug,
            heading: ref.heading,
            mode: ref.mode,
            reason: "not_found_or_unpublished",
          });
        }
      }
      return { ok: broken.length === 0, broken, checked: refs.length };
    },

    async list_page_headings(args) {
      const slug = String(args.slug || "").trim();
      if (!slug) return { error: "slug is required." };

      let payload;
      try {
        payload = await this.executeTool("read_page_content", { slug });
      } catch (e) {
        return { error: `Failed to read page: ${e.message}` };
      }
      if (payload && payload.error) return payload;

      const store = window.Alpine && Alpine.store("app");
      if (store && typeof store.extractPageHeadings === "function") {
        let meta = null;
        try {
          meta = await this.executeTool("read_page_metadata", { slug });
        } catch (_) {
          /* optional */
        }
        return store.extractPageHeadings(
          {
            body: payload?.body || payload?.content || "",
            content: payload?.body || payload?.content || "",
            partials: payload?.partials || {},
            frontmatter: meta?.frontmatter || payload?.frontmatter || {},
            composite_partials:
              meta?.frontmatter?.partials ||
              meta?.partials ||
              meta?.composite_partials ||
              null,
            composite: !!payload?.composite,
          },
          slug,
        );
      }

      // Fallback if store helper is unavailable
      const headings = [];
      const body = payload?.body || payload?.content || "";
      for (const line of String(body).replace(/\r/g, "").split("\n")) {
        const match = line.match(/^(#{1,3})\s+(.*)$/);
        if (match) {
          headings.push({
            level: match[1].length,
            title: match[2].trim(),
            source: "body",
          });
        }
      }
      return { slug, headings, composite: !!payload?.composite };
    },

    // Markdown-to-HTML rendering is delegated to `marked` (see module-scope
    // `md`/`innerMd` configuration at the top of this file). The `md`
    // instance is configured once and never mutated after init — the role
    // is passed in via the module-scoped `_currentRole` closure variable,
    // not via `md.use()` per render, to avoid a streaming-time race.
    renderMsg(msgOrContent, isLast = false) {
      if (!msgOrContent) return "";

      let content = "";
      let role = "assistant";
      let name = "";
      let toolCalls = null;

      if (typeof msgOrContent === "object" && msgOrContent !== null) {
        content = msgOrContent.displayContent || msgOrContent.content || "";
        role = msgOrContent.role || "assistant";
        name = msgOrContent.name || "";
        toolCalls = msgOrContent.tool_calls || null;

        // If content is a multimodal array (from a message without displayContent),
        // extract text parts and render image parts as thumbnails.
        if (Array.isArray(content)) {
          const textParts = content
            .filter((p) => p.type === "text" && p.text)
            .map((p) => p.text);
          const imageParts = content.filter((p) => p.type === "image_url");
          let html = "";
          if (textParts.length) {
            html += textParts.join("\n\n");
          }
          if (imageParts.length) {
            html += "\n\n";
            for (const img of imageParts) {
              const url = img.image_url?.url || "";
              if (url) {
                html += `<img src="${url}" class="max-h-40 rounded border border-border my-1" style="display:block" />`;
              }
            }
          }
          content = html;
        }
      } else {
        content = String(msgOrContent);
      }

      if (content) {
        content = content.replace(/\r\n/g, "\n");
        content = content.replace(/```tool_call[\s\S]*?```/g, "");
        content = content.replace(/```json[\s\S]*?```/g, "");
        content = content.replace(/脚本/g, "");

        const rawJsonRegex = /\{[\s\S]*?\}/g;
        content = content.replace(rawJsonRegex, (match) => {
          try {
            const parsed = JSON.parse(match);
            if (
              parsed.name ||
              parsed.query ||
              parsed.slug ||
              parsed.filename ||
              parsed.collection_name
            ) {
              return "";
            }
          } catch (e) {}
          return match;
        });

        content = content.trim();
      }

      if (role === "tool") {
        let extraHtml = "";
        if (["generate_media", "write_media_file"].includes(name)) {
          try {
            const resObj = JSON.parse(content);
            if (resObj && resObj.public_url) {
              let url = resObj.public_url;
              // Apply cache buster if available
              const buster =
                this.mediaCacheBusters &&
                msgOrContent.tool_call_id &&
                this.mediaCacheBusters[msgOrContent.tool_call_id];
              if (buster) {
                url = `${url}?t=${buster}`;
              }

              let regenerateBtn = "";
              if (name === "generate_media" && msgOrContent.tool_call_id) {
                regenerateBtn = `
                  <div class="flex items-center gap-2 mt-1.5 select-none">
                    <button type="button"
                            @click="regenerateMedia('${msgOrContent.tool_call_id}', $event)"
                            class="flex items-center gap-1 px-1.5 py-0.5 bg-card hover:bg-rust-wash/20 text-forge-black hover:text-rust border border-border hover:border-rust text-[9px] font-bold uppercase tracking-wider transition-colors outline-none shrink-0 shadow-sm">
                      <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                      </svg>
                      <span>Regenerate</span>
                    </button>
                  </div>
                `;
              }

              extraHtml = `
                <div class="mt-2 flex flex-col gap-0.5">
                  <div class="w-32 h-32 rounded border border-border bg-canvas overflow-hidden relative cursor-pointer group/thumb hover:border-rust transition-colors shadow-sm"
                       @click="openModalImage('${url}')">
                    <img src="${url}" class="w-full h-full object-cover" />
                    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover/thumb:opacity-100 transition-opacity duration-200 flex items-center justify-center">
                      <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7"></path>
                      </svg>
                    </div>
                  </div>
                  ${
                    resObj.relative_path || resObj.use_for_embedding
                      ? `<div class="text-[9px] font-mono text-steel-muted max-w-[12rem] break-all leading-snug" title="Use this path in [image src] / hero_image">Embed path: ${
                          resObj.relative_path || resObj.use_for_embedding
                        }</div>`
                      : ""
                  }
                  ${regenerateBtn}
                </div>
              `;
            }
          } catch (e) {
            console.warn("Failed to parse tool result for thumbnail:", e);
          }
        }

        return `<div class="text-[10px] font-mono text-steel-muted flex flex-col gap-1.5 py-0 select-text">
          <div class="flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5 text-steel-muted shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
            </svg>
            <span>Tool <strong>${name || "mcp"}</strong> executed.</span>
          </div>
          ${extraHtml}
        </div>`;
      }

      if (
        role === "assistant" &&
        toolCalls &&
        toolCalls.length > 0 &&
        !content
      ) {
        const toolNames = toolCalls.map((tc) => tc.function.name).join(", ");
        if (this.streaming && isLast) {
          return `<div class="text-[10px] font-mono text-rust flex items-center gap-1.5 py-0">
            <svg class="w-3.5 h-3.5 text-rust animate-spin shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            <span>Calling tool: <strong>${toolNames}</strong>...</span>
          </div>`;
        } else {
          return `<div class="text-[10px] font-mono text-steel-muted flex items-center gap-1.5 py-0 select-text">
            <svg class="w-3.5 h-3.5 text-steel-muted shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
            </svg>
            <span>Requested tool: <strong>${toolNames}</strong></span>
          </div>`;
        }
      }

      if (!content) return "";

      // Snapshot the role for this parse so the paragraph renderer can read
      // leading-tight vs leading-relaxed from the closure. Updated
      // synchronously before each parse; the closure inside the renderer
      // reads it. The `md` instance itself is never mutated after init.
      _currentRole = role;
      return md.parse(content);
    },
  }));

  Alpine.data("aiCommandOverlay", () => ({
    commandText: "",
    hasSelection: false,
    selectionText: "",
    selectionWordCount: 0,
    selectionPreview: "",

    init() {
      // Register global keyboard shortcut Ctrl+K or Cmd+K
      window.addEventListener(
        "keydown",
        (e) => {
          if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            e.stopPropagation();
            this.openOverlay();
          }
        },
        true,
      );

      // Fallback click listener for backdrop dismiss on browsers that don't support closedby="any"
      const dialog = document.getElementById("ai-command-overlay");
      if (dialog && !("closedBy" in HTMLDialogElement.prototype)) {
        dialog.addEventListener("click", (event) => {
          if (event.target !== dialog) return;
          const rect = dialog.getBoundingClientRect();
          const isDialogContent =
            rect.top <= event.clientY &&
            event.clientY <= rect.top + rect.height &&
            rect.left <= event.clientX &&
            event.clientX <= rect.left + rect.width;
          if (isDialogContent) return;
          this.closeOverlay();
        });
      }
    },

    openOverlay() {
      this.commandText = "";

      // Capture text selection at the moment of opening
      const editor = window.getPenEditor?.();
      if (editor) {
        const doc = editor.getValue();
        const view = editor.getView?.();
        if (view) {
          const range = view.state.selection.main;
          if (range && !range.empty) {
            this.selectionText = doc.slice(range.from, range.to);
            this.hasSelection = true;
            this.selectionWordCount = this.selectionText
              .trim()
              .split(/\s+/)
              .filter(Boolean).length;
            const preview = this.selectionText.trim();
            this.selectionPreview =
              preview.length > 35
                ? `"${preview.substring(0, 35)}..."`
                : `"${preview}"`;
          } else {
            this.hasSelection = false;
            this.selectionText = "";
            this.selectionWordCount = 0;
            this.selectionPreview = "";
          }
        }
      } else {
        this.hasSelection = false;
        this.selectionText = "";
        this.selectionWordCount = 0;
        this.selectionPreview = "";
      }

      const dialog = document.getElementById("ai-command-overlay");
      if (dialog && !dialog.open) {
        dialog.showModal();
        this.$nextTick(() => {
          this.$refs.input.focus();
        });
      }
    },

    closeOverlay() {
      const dialog = document.getElementById("ai-command-overlay");
      if (dialog && dialog.open) {
        dialog.close();
      }
    },

    submitCommand() {
      const cmd = this.commandText.trim();
      if (!cmd) return;

      this.closeOverlay();

      const detail = { command: cmd };
      if (this.hasSelection && this.selectionText) {
        detail.selection = this.selectionText;
        const editor = window.getPenEditor?.();
        const view = editor?.getView?.();
        const selection = view?.state?.selection?.main;
        if (selection && !selection.empty) {
          detail.selectionRange = {
            from: selection.from,
            to: selection.to,
            editorName:
              (window.Alpine && Alpine.$data(document.body)?.activePartial) ||
              "main",
          };
        }
      }

      window.dispatchEvent(new CustomEvent("pen:ai-command", { detail }));
    },
  }));
});

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".copy-code-btn");
  if (!btn) return;

  if (!navigator.clipboard) {
    console.warn("Clipboard access not supported in this browser.");
    return;
  }
  const pre = btn.previousElementSibling;
  if (!pre) return;
  const code = pre.querySelector("code");
  if (!code) return;

  const text = code.textContent;

  navigator.clipboard
    .writeText(text)
    .then(() => {
      // Find the aiSidebar Alpine component to show toast
      const aiSidebarEl = document.querySelector('[x-data="aiSidebar"]');
      if (aiSidebarEl && window.Alpine) {
        const aiSidebar = window.Alpine.$data(aiSidebarEl);
        if (aiSidebar && typeof aiSidebar.showToast === "function") {
          aiSidebar.showToast("Copied code block to clipboard.");
        }
      }

      // Switch to checkmark SVG
      const originalHTML = btn.innerHTML;
      btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4"><rect width="256" height="256" fill="none"/><polyline points="40 144 96 200 224 72" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>`;
      btn.classList.add("text-green-600");
      btn.classList.remove("text-forge-mid", "hover:text-rust");

      setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.classList.remove("text-green-600");
        btn.classList.add("text-forge-mid", "hover:text-rust");
      }, 2000);
    })
    .catch((err) => {
      console.error("Failed to copy code block: ", err);
    });
});
