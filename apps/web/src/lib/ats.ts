// The ATS report in the words and groups the UI shows (docs/PRODUCT.md, 9).
import type { AtsBand, AtsKeyword, AtsReport, JobSummary } from '#lib/cv/types.ts';

export const BAND_LABELS: Record<AtsBand, string> = {
	strong: 'Strong match',
	good: 'Good match',
	partial: 'Partial match',
	limited: 'Limited match'
};

export interface KeywordGroups {
	found: AtsKeyword[];
	/** Missing from the CV, but the profile it came from has them: they can go back in. */
	leftOut: AtsKeyword[];
	/** Missing from the CV and from its profile: only for the profile, and only if true. */
	notInProfile: AtsKeyword[];
	/** Missing from a CV that has no profile to look in. */
	notInCv: AtsKeyword[];
	/** Found only in the skills list, not in a role or project. */
	skillsOnly: AtsKeyword[];
}

export function keywordGroups(report: AtsReport): KeywordGroups {
	const found = report.keywords.filter((k) => k.found_in.length > 0);
	const missing = report.keywords.filter((k) => k.found_in.length === 0);
	return {
		found,
		leftOut: missing.filter((k) => k.in_profile === true),
		notInProfile: missing.filter((k) => k.in_profile === false),
		notInCv: missing.filter((k) => k.in_profile == null),
		skillsOnly: found.filter((k) => k.found_in.length === 1 && k.found_in[0] === 'skills')
	};
}

/** "12 of 15 job keywords are in this CV." */
export function coverage(report: AtsReport): string {
	const total = report.keywords.length;
	const found = report.keywords.filter((k) => k.found_in.length > 0).length;
	return `${found} of ${total} job ${total === 1 ? 'keyword is' : 'keywords are'} in this CV.`;
}

/** Whether the headline or a role names the job, as a recruiter's title search looks for. */
export function titleLine(report: AtsReport): string | null {
	if (!report.title) return null;
	return report.title_found
		? `Your headline or a role says "${report.title}".`
		: `Your headline and roles do not say "${report.title}". Use it in your headline if it describes you.`;
}

/** "Data engineer at Harbour Bank", or the title alone. */
export function jobLabel(job: Pick<JobSummary, 'title' | 'company'>): string {
	const title = job.title || 'Untitled job';
	return job.company ? `${title} at ${job.company}` : title;
}
