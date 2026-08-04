// Lightweight markdown-ish renderer for local-LLM output (Ollama/phi3:mini).
// Extracted from the pattern already used on Dashboard.tsx's AI insight panel
// so every AI-generated markdown blob in the app (daily insight, deal
// momentum, and now the MOM) renders the same way, instead of each screen
// re-inventing it — or reaching for a full markdown library (react-markdown)
// for output that's only ever headers/bold/bullets/newlines in practice.
export function renderMarkdownLite(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color:inherit;font-weight:700">$1</strong>')
    .replace(/^#{1,3}\s(.+)$/gm, '<div style="font-weight:700;margin-top:10px;margin-bottom:2px">$1</div>')
    .replace(/^-\s(.+)$/gm, '<div style="padding-left:14px;position:relative">&bull;&nbsp; $1</div>')
    .replace(/\n{2,}/g, '<br/>')
    .replace(/\n/g, '<br/>')
}
