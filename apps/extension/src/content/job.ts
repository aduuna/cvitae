import type { JobDraft } from './types.ts';

/** The api's limit on a job description. */
export const MAX_DESCRIPTION = 30_000;
const MIN_SELECTION = 200;

type Json = Record<string, unknown>;

function isPosting(value: unknown): value is Json {
	const type = (value as Json | null)?.['@type'];
	return type === 'JobPosting' || (Array.isArray(type) && type.includes('JobPosting'));
}

/** The first JobPosting in the page's structured data (schema.org JSON-LD), which job boards
 * publish for search engines. */
export function findPosting(doc: Document): Json | null {
	for (const script of doc.querySelectorAll('script[type="application/ld+json"]')) {
		let data: unknown;
		try {
			data = JSON.parse(script.textContent ?? '');
		} catch {
			continue;
		}
		const queue: unknown[] = [data];
		while (queue.length) {
			const item = queue.shift();
			if (isPosting(item)) return item;
			if (Array.isArray(item)) queue.push(...item);
			else if (item && typeof item === 'object' && '@graph' in item) {
				queue.push((item as Json)['@graph']);
			}
		}
	}
	return null;
}

const BLOCKS = new Set([
	'P',
	'DIV',
	'LI',
	'UL',
	'OL',
	'H1',
	'H2',
	'H3',
	'H4',
	'H5',
	'H6',
	'BR',
	'SECTION',
	'ARTICLE',
	'TR'
]);

/**
 * Readable text from HTML: one line per paragraph or list item, list items with a dash. Some
 * boards escape the HTML in their posting data a second time; that is decoded too.
 */
export function htmlToText(html: string): string {
	const parse = (source: string) => new DOMParser().parseFromString(source, 'text/html').body;
	let body = parse(html);
	if (!body.querySelector('*') && /<\/?[a-z][^>]*>/i.test(body.textContent ?? '')) {
		body = parse(body.textContent ?? '');
	}
	return nodeText(body);
}

function nodeText(root: Node, skipForms = true): string {
	const lines: string[] = [];
	let line = '';
	const flush = () => {
		if (line.trim()) lines.push(line.replace(/\s+/g, ' ').trim());
		line = '';
	};
	const walk = (node: Node) => {
		for (const child of node.childNodes) {
			if (child.nodeType === Node.TEXT_NODE) {
				line += child.textContent ?? '';
			} else if (child instanceof Element) {
				if (/^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|SVG|BUTTON|NAV|FOOTER)$/i.test(child.tagName))
					continue;
				// The application form's labels are not part of the ad.
				if (skipForms && child.tagName === 'FORM') continue;
				const block = BLOCKS.has(child.tagName);
				if (block) flush();
				if (child.tagName === 'LI') line += '- ';
				walk(child);
				if (block) flush();
			}
		}
	};
	walk(root);
	flush();
	return lines.join('\n');
}

function text(value: unknown): string {
	return typeof value === 'string' ? value.trim() : '';
}

function meta(doc: Document, property: string): string {
	return text(
		doc
			.querySelector(`meta[property="${property}"], meta[name="${property}"]`)
			?.getAttribute('content')
	);
}

/** The page's address without its fragment and tracking parameters. */
export function cleanUrl(href: string): string {
	try {
		const url = new URL(href);
		url.hash = '';
		for (const key of [...url.searchParams.keys()]) {
			// gh_jid stays: it is the Greenhouse job a company's careers page shows.
			if (/^(utm_|gh_src$|lever-|ref$|source$|src$)/.test(key)) url.searchParams.delete(key);
		}
		return url.toString();
	} catch {
		return href;
	}
}

/** The job board's name for the company, from paths like boards.greenhouse.io/<company>/jobs. */
function companyFromUrl(href: string): string {
	try {
		const url = new URL(href);
		const first = url.pathname.split('/').filter(Boolean)[0] ?? '';
		if (/(^|\.)greenhouse\.io$|(^|\.)lever\.co$|(^|\.)ashbyhq\.com$/.test(url.hostname) && first) {
			return first.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
		}
	} catch {
		// Fall through.
	}
	return '';
}

function mainText(doc: Document): string {
	const main = doc.querySelector(
		'[class*="job-description" i], [id*="job-description" i], [class*="jobDescription"], main, article, [role="main"]'
	);
	const root = main ?? doc.body;
	// Some sites put the whole page in one form; then the form is the content.
	return nodeText(root) || nodeText(root, false);
}

/** The job ad on this page, or null when there is no text to save. */
export function readJob(doc: Document = document): JobDraft | null {
	const url = cleanUrl(
		doc.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href || doc.location.href
	);
	const posting = findPosting(doc);
	const organization = posting?.['hiringOrganization'];
	// On a job board the site's name may be the board's; its path names the company.
	const company =
		text((organization as Json | undefined)?.['name'] ?? organization) ||
		companyFromUrl(url) ||
		meta(doc, 'og:site_name');
	const title =
		text(posting?.['title']) ||
		meta(doc, 'og:title') ||
		text(doc.querySelector('h1')?.textContent) ||
		doc.title.trim();

	const selection = doc.getSelection?.()?.toString().trim() ?? '';
	const [found, from]: [string, JobDraft['from']] =
		posting && text(posting['description'])
			? [htmlToText(text(posting['description'])), 'posting']
			: selection.length >= MIN_SELECTION
				? [selection, 'selection']
				: [mainText(doc), 'page'];
	const description = found.slice(0, MAX_DESCRIPTION).trim();
	if (!description) return null;
	return { title: title.slice(0, 200), company: company.slice(0, 200), url, description, from };
}
