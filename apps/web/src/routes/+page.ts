// The landing page is built to static HTML, so search engines and link previews read its content
// without running the app. Every other page stays client-rendered (root +layout.ts).
export const ssr = true;
export const prerender = true;
