/**
 * Job application platforms the extension may read at install, so it can offer to fill their
 * forms without asking each time. Other sites work when the user opens the extension there
 * (the toolbar button gives it that one tab) or allows the site in the side panel.
 */
export const JOB_SITES: readonly { name: string; patterns: readonly string[] }[] = [
	{ name: 'Greenhouse', patterns: ['https://*.greenhouse.io/*'] },
	{ name: 'Lever', patterns: ['https://*.lever.co/*'] },
	{ name: 'Workday', patterns: ['https://*.myworkdayjobs.com/*', 'https://*.myworkdaysite.com/*'] },
	{ name: 'Ashby', patterns: ['https://jobs.ashbyhq.com/*'] },
	{ name: 'SmartRecruiters', patterns: ['https://jobs.smartrecruiters.com/*'] },
	{ name: 'Workable', patterns: ['https://apply.workable.com/*'] },
	{ name: 'BambooHR', patterns: ['https://*.bamboohr.com/*'] },
	{ name: 'iCIMS', patterns: ['https://*.icims.com/*'] },
	{ name: 'Taleo', patterns: ['https://*.taleo.net/*'] },
	{
		name: 'SuccessFactors',
		patterns: ['https://*.successfactors.com/*', 'https://*.successfactors.eu/*']
	},
	{ name: 'Avature', patterns: ['https://*.avature.net/*'] },
	{ name: 'Jobvite', patterns: ['https://jobs.jobvite.com/*'] },
	{ name: 'Recruitee', patterns: ['https://*.recruitee.com/*'] },
	{ name: 'Teamtailor', patterns: ['https://*.teamtailor.com/*'] },
	{ name: 'Personio', patterns: ['https://*.jobs.personio.com/*', 'https://*.jobs.personio.de/*'] },
	{ name: 'Breezy HR', patterns: ['https://*.breezy.hr/*'] }
];

export const JOB_SITE_PATTERNS: readonly string[] = JOB_SITES.flatMap((site) => site.patterns);

/** Whether a URL matches an extension match pattern such as "https://*.lever.co/*". */
export function matchesPattern(href: string, pattern: string): boolean {
	const match = /^(\*|https?):\/\/([^/]+)(\/.*)$/.exec(pattern);
	if (!match) return false;
	const [, scheme, host = '', path = ''] = match;
	let url: URL;
	try {
		url = new URL(href);
	} catch {
		return false;
	}
	if (scheme !== '*' && url.protocol !== `${scheme}:`) return false;
	const hostOk = host.startsWith('*.')
		? url.hostname === host.slice(2) || url.hostname.endsWith(host.slice(1))
		: host === '*' || url.hostname === host;
	const pathRe = new RegExp(`^${path.split('*').map(escape).join('.*')}$`);
	return hostOk && pathRe.test(url.pathname + url.search);
}

function escape(text: string): string {
	return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** The job platform a page is on, if it is one the extension knows. */
export function jobSite(href: string): string | null {
	return JOB_SITES.find((site) => site.patterns.some((p) => matchesPattern(href, p)))?.name ?? null;
}
