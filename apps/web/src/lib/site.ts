/** The public address of the site, for canonical links, link previews, robots.txt and the sitemap. */
export const SITE_URL = 'https://cvitae.aduuna.dev';

export const SITE_NAME = 'Chameleon vitae';

/** Where people write about their data (the privacy policy) and the extension's store listings. */
export const CONTACT_EMAIL = 'privacy@aduuna.dev';

/** Other names people search for; search engines read them from the structured data below. */
export const SITE_ALTERNATE_NAMES = ['cvitae', 'Chameleon CV'];

/** The landing page's title and description, as search results and link previews show them. */
export const SITE_TITLE = 'Chameleon vitae: a CV tailored to every job';
export const SITE_DESCRIPTION =
	'Chameleon vitae (cvitae) adapts your CV to every job, like a chameleon. Import your CV, paste a job description and get a tailored CV, a cover letter in your tone and an ATS score.';

/**
 * schema.org data for the landing page: the site's name and alternate names (which search engines
 * use for the site name in results) and what the app is. A JSON-LD script tag, ready for the head.
 */
export function structuredData(): string {
	const site = {
		name: SITE_NAME,
		alternateName: SITE_ALTERNATE_NAMES,
		url: `${SITE_URL}/`
	};
	const json = JSON.stringify([
		{ '@context': 'https://schema.org', '@type': 'WebSite', ...site },
		{
			'@context': 'https://schema.org',
			'@type': 'WebApplication',
			...site,
			description: SITE_DESCRIPTION,
			applicationCategory: 'BusinessApplication',
			operatingSystem: 'Web'
		}
	]);
	// "<" escaped so nothing in the data can close the script tag early.
	return `<script type="application/ld+json">${json.replaceAll('<', '\\u003c')}</script>`;
}
