# AI MCP is the job of PenCMS, not TravenEditor

For an **embedded editor (like Traven inside a CMS)**, the **UI-pure, API-driven approach (Traven's model)** is objectively superior for both the developers building the host application and the end-users writing in it. 

Here is why, broken down by perspective:

---

### 1. The Developer's Perspective (Building the CMS)
If you are a developer embedding an editor into a CMS, a built-in AI in the editor is actually a liability.

* **Context Lock-in:** Inside a CMS, writing does not happen in a vacuum. A writer needs the AI to know about things *outside* the body text: the target SEO keywords (entered in another field), the product catalog database, the brand voice guidelines, or related articles. A built-in AI only knows the text engine. An API-driven editor allows the host application to feed the LLM the entire CMS context.
* **Security & Compliance:** Enterprise CMS clients often have strict data privacy requirements. They might forbid sending data to OpenAI/Anthropic and require routing prompts through a self-hosted model (like Llama 3 via Ollama) or a corporate proxy. If the editor has built-in AI, routing it through custom security layers is incredibly difficult. If the host handles the AI calls, it is trivial.
* **Cost & Billing:** AI tokens cost money. If the editor has built-in AI, the host developer has to figure out who pays for the editor's subscription. With Traven's approach, the host application uses its own API keys or bills the client directly based on usage.

---

### 2. The End-User's Perspective (The Content Writer)
For the writer inside a CMS, the editing experience is much better when the AI is a **first-class citizen of the CMS**, not just the text box.

* **Unified UI:** Instead of having one AI panel for editing text, another for generating SEO tags, and another for writing social media captions, a host-managed AI can control all of these. The host can provide a single, cohesive sidebar widget that has access to the fields around the document *and* the document content inside Traven.
* **Multi-field Generation:** A host-managed AI can write the blog post inside Traven and simultaneously populate the "SEO Description" and "Suggested URL Slug" input fields in the CMS. A built-in editor assistant cannot escape its own text box to edit other HTML inputs on the page.

---

### Summary: The "Correct" Separation of Concerns

Exposing MCP at the editor level is an architectural mismatch for an embedded library. 

* **Traven's approach** is the industry standard for **headless/embedded software** (like TipTap or Lexical). If you look at TipTap, they offer AI features, but they do so by offering modular extensions that hook into the developer's API endpoints rather than hardcoding LLM clients into the core text parser.

**Verdict:** Keep Traven UI-pure. Focus 100% of your energy on making the **Markdown parser robust, fast, and highly exposed via API hooks** (`getMarkdownState()`, `replaceSelection()`, etc.). That is exactly what CMS developers want.

---

Here is why a CMS developer will be relieved that Traven does **not** ship with a built-in MCP server, and why MCP belongs entirely at the **host/platform level**:

---

### 1. The Scope of the "Context"
MCP is designed to give AI agents access to data sources and tools. In a CMS, the text inside the editor is only a tiny fraction of the data an AI agent needs:
* **The Editor's View:** A Traven MCP server would only be able to say: *"Here is the Markdown text of the article currently open."*
* **The CMS's View:** A CMS MCP server can say: *"Here are the 500 published articles, the media library containing 2,000 images, the user directory, the draft history, and the taxonomy tags."*

If a developer wants an AI agent to write a new blog post based on existing content, the agent needs to search the CMS database, look at the asset library to insert images, and set tags. A Traven-provided MCP server would be blind to all of this.

---

### 2. Security, Authentication, and Transport
MCP servers communicate either via `stdio` (for local CLI agents) or `SSE` (Server-Sent Events over HTTP for remote/web-based agents). 

In a production CMS environment:
* Exposing an MCP server requires securing the endpoint with OAuth, JWTs, rate-limiting, and Role-Based Access Control (RBAC). (e.g., *Can this AI agent publish a page, or only save a draft?*)
* The editor runs in the user's browser, whereas the source of truth (the database) lives on the server. 
* A text editor library simply doesn't have the infrastructure or authorization to negotiate these protocols. The host application backend **must** act as the gateway.

---

### 3. The Local Flat-File Cheat Code
For developers working locally on desktop applications (where the workspace is just a folder of `.md` files):
* They don't need a custom Traven MCP server anyway.
* The official, standard **Filesystem MCP Server** (maintained by Anthropic) already gives agents full read/write access to any folder on the machine. 
* Because Traven saves content in pure Markdown, any off-the-shelf filesystem MCP server can read and write Traven's files natively. There is no custom protocol required.

---

### Conclusion
By keeping Traven free of MCP bloat:
1. **You keep the bundle size small** and avoid pulling in Node/browser compatibility shims or SSE networking libraries.
2. **You avoid security vulnerabilities** inherent in exposing web sockets or event streams from an editor component.
3. **You empower CMS developers** to build a single, comprehensive MCP server on their backend that handles database queries, asset management, *and* updates the markdown text using Traven's clean API.

---

For a FOSS project like Traven Editor, the goals are:
* **Simplicity & Reliability:** The code only needs to do one thing—provide an exceptional Markdown editing experience—and do it perfectly. 
* **Longevity:** Because it doesn't rely on external APIs (like OpenAI or custom cloud sync services), a version of Traven that works today will still work exactly the same way in five or ten years, with zero maintenance costs or breaking API updates.
* **Pure Integration:** Traven is designed to be a building block. It respects the host developer's environment by not forcing decisions (like AI vendors or network layers) onto them.

By staying UI-pure and focused on the data layer, Traven remains a lightweight, transparent, and highly versatile tool that developers can trust for the long haul.

And by focusing on outputting clean, standard-compliant Markdown, Traven guarantees that any content created in it is immediately "future-proofed" for AI agents, RAG engines, and whatever comes next in the developer ecosystem. 

It is the ultimate expression of the UNIX philosophy: do one thing, do it exceptionally well, and make sure it plays nicely with other tools. 

AI integration belongs in the host application, which is PenCMS, and not in Traven Editor.

---

## Related PenCMS features (host-owned)

PenCMS now uses Traven’s generic hooks for site-aware editing without putting CMS logic in the editor bundle:

* **Link suggestions** — `onSuggestLinks` in the Insert Link modal (published posts/pages for the active Content site).
* **Heading picker** — `onListHeadings` for Expand/Embed section dropdown once a slug is chosen.
* **`[expand]` / `[embed]`** — loaded as `ExpandEmbedPlugin` via `options.plugins`; public HTML resolved by PHP (`ExpandResolver` / `ShortcodeProcessor`).
* **AI / MCP catalog tools** — `suggest_internal_links`, `insert_expand_embed` / `list_page_headings` / `check_expand_refs` (sidebar); MCP exposes `suggest_internal_links` + `check_expand_refs` (insert via `write_content_file`). Shared live-published catalog (`publish_at`-aware) lives in PenCMS only.

Canonical usage and architecture: [`editor-link-suggest-and-expand.md`](./editor-link-suggest-and-expand.md).



