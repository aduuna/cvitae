import type { ExtensionSession } from './api.ts';
import type { SourceRef } from './settings.ts';

type Job = ExtensionSession['jobs'][number];

/**
 * A job ad's identity across the pages of one application. Greenhouse and Lever have their own
 * ids (an ad, its application form and an embedded copy on the company's site share one); any
 * other ad is its host and path, and the pages under it ("/apply") belong to it.
 */
export function jobKey(href: string): { id: string } | { prefix: string } | null {
	let url: URL;
	try {
		url = new URL(href);
	} catch {
		return null;
	}
	const host = url.hostname.replace(/^www\./, '').toLowerCase();
	const parts = url.pathname.split('/').filter(Boolean);
	const greenhouse =
		url.searchParams.get('gh_jid') ??
		(host.endsWith('greenhouse.io')
			? (url.searchParams.get('token') ?? (parts[1] === 'jobs' && parts[2] ? parts[2] : null))
			: null);
	if (greenhouse && /^\d+$/.test(greenhouse)) return { id: `greenhouse:${greenhouse}` };
	if (host.endsWith('lever.co') && parts[1] && /^[0-9a-f-]{36}$/i.test(parts[1])) {
		return { id: `lever:${parts[1].toLowerCase()}` };
	}
	return { prefix: `${host}/${parts.join('/')}`.toLowerCase() };
}

function sameJob(job: Job, pageUrl: string): number {
	if (!job.url) return 0;
	const saved = jobKey(job.url);
	const page = jobKey(pageUrl);
	if (!saved || !page) return 0;
	if ('id' in saved || 'id' in page)
		return 'id' in saved && 'id' in page && saved.id === page.id ? 1000 : 0;
	const { prefix } = saved;
	return page.prefix === prefix || page.prefix.startsWith(`${prefix}/`) ? prefix.length : 0;
}

/** The saved job whose ad this page is, or its application; the most specific match wins. */
export function jobForPage(jobs: Job[], pageUrls: (string | undefined)[]): Job | null {
	let best: Job | null = null;
	let score = 0;
	for (const job of jobs) {
		for (const url of pageUrls) {
			const s = url ? sameJob(job, url) : 0;
			if (s > score) [best, score] = [job, s];
		}
	}
	return best;
}

export interface Suggestion {
	source: SourceRef;
	/** Why: the CV tailored for this page's job, the user's last choice, or the default profile. */
	reason: 'job' | 'chosen' | 'default';
	job: Job | null;
}

function exists(session: ExtensionSession, source: SourceRef): boolean {
	const list = source.kind === 'profile' ? session.profiles : session.documents;
	return list.some((item) => item.id === source.id);
}

/** What to fill this page from. A CV tailored for the page's job comes first. */
export function suggestSource(
	session: ExtensionSession,
	pageUrls: (string | undefined)[],
	chosen: SourceRef | null
): Suggestion | null {
	const job = jobForPage(session.jobs, pageUrls);
	const tailored = job && session.documents.find((doc) => doc.job_id === job.id);
	if (tailored) return { source: { kind: 'document', id: tailored.id }, reason: 'job', job };
	if (chosen && exists(session, chosen)) return { source: chosen, reason: 'chosen', job };
	const profile = session.profiles.find((p) => p.is_default) ?? session.profiles[0];
	if (profile) return { source: { kind: 'profile', id: profile.id }, reason: 'default', job };
	const cv = session.documents[0];
	return cv ? { source: { kind: 'document', id: cv.id }, reason: 'default', job } : null;
}

/** How a source reads in a sentence: "Backend profile", "Acme data engineer CV". */
export function sourceName(session: ExtensionSession, source: SourceRef): string {
	if (source.kind === 'profile') {
		const name = session.profiles.find((p) => p.id === source.id)?.name ?? 'profile';
		return /\bprofile\b/i.test(name) ? name : `${name} profile`;
	}
	const name = session.documents.find((d) => d.id === source.id)?.name ?? 'CV';
	return /\bcv\b/i.test(name) ? name : `${name} CV`;
}
