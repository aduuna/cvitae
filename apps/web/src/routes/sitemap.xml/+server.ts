import { SITE_URL } from '#lib/site.ts';

export const prerender = true;

export function GET(): Response {
	const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
	<url><loc>${SITE_URL}/</loc></url>
</urlset>
`;
	return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
}
