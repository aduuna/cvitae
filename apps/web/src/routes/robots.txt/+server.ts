import { SITE_URL } from '#lib/site.ts';

export const prerender = true;

// Only the landing page is public; the app and sign-in pages are for signed-in use.
export function GET(): Response {
	const body = [
		'User-agent: *',
		'Disallow: /app/',
		'Disallow: /auth/',
		'Disallow: /api/',
		'',
		`Sitemap: ${SITE_URL}/sitemap.xml`,
		''
	].join('\n');
	return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}
