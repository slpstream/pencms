/**
 * Shared sanitizer for AI sidebar marked output (editor, navigation, customize).
 * Fail closed if the vendored DOMPurify script did not load.
 */
function sanitizeAiMarkdownHtml(html) {
  if (typeof DOMPurify === "undefined") return "";
  return DOMPurify.sanitize(String(html ?? ""), {
    USE_PROFILES: { html: true, svg: true },
    FORBID_TAGS: ["form", "style"],
    ADD_ATTR: ["target"],
  });
}
