import { describe, expect, it } from 'vitest';
import type { ExtensionSession } from '../src/lib/api.ts';
import { jobForPage, jobKey, sourceName, suggestSource } from '../src/lib/sources.ts';

const at = '2026-10-01T09:00:00Z';

function session(overrides: Partial<ExtensionSession> = {}): ExtensionSession {
	return {
		email: 'ada@example.com',
		display_name: null,
		profiles: [
			{ id: 'p-backend', name: 'Backend', is_default: false, updated_at: at },
			{ id: 'p-data', name: 'Data engineering', is_default: true, updated_at: at }
		],
		documents: [
			{
				id: 'd-harbour',
				name: 'Harbour Bank CV',
				job_id: 'j-harbour',
				placeholders: 0,
				updated_at: at
			},
			{ id: 'd-plain', name: 'General', job_id: null, placeholders: 1, updated_at: at }
		],
		jobs: [
			{
				id: 'j-harbour',
				title: 'Data engineer',
				company: 'Harbour Bank',
				url: 'https://boards.greenhouse.io/harbour/jobs/4012345',
				created_at: at,
				updated_at: at
			},
			{
				id: 'j-meridian',
				title: 'Analytics engineer',
				company: 'Meridian',
				url: 'https://meridian.example.com/careers/analytics-engineer',
				created_at: at,
				updated_at: at
			}
		],
		...overrides
	};
}

describe('jobKey', () => {
	it('knows the ids Greenhouse and Lever use on every page of an application', () => {
		const id = { id: 'greenhouse:4012345' };
		expect(jobKey('https://boards.greenhouse.io/harbour/jobs/4012345#app')).toEqual(id);
		expect(
			jobKey('https://job-boards.greenhouse.io/embed/job_app?for=harbour&token=4012345')
		).toEqual(id);
		expect(jobKey('https://harbourbank.com/careers/open-roles?gh_jid=4012345')).toEqual(id);
		const lever = 'https://jobs.lever.co/acme/0d2c9a10-1b2c-4d5e-8f90-a1b2c3d4e5f6';
		expect(jobKey(`${lever}/apply`)).toEqual({ id: 'lever:0d2c9a10-1b2c-4d5e-8f90-a1b2c3d4e5f6' });
		expect(jobKey('https://www.Example.com/Jobs/42/')).toEqual({ prefix: 'example.com/jobs/42' });
		expect(jobKey('not a url')).toBeNull();
	});
});

describe('jobForPage', () => {
	const { jobs } = session();

	it('matches the ad, its application form and an embedded copy', () => {
		expect(
			jobForPage(jobs, ['https://job-boards.greenhouse.io/embed/job_app?for=harbour&token=4012345'])
				?.id
		).toBe('j-harbour');
		expect(
			jobForPage(jobs, ['https://meridian.example.com/careers/analytics-engineer/apply'])?.id
		).toBe('j-meridian');
	});

	it('does not match another job on the same site', () => {
		expect(
			jobForPage(jobs, ['https://meridian.example.com/careers/analytics-engineer-2'])
		).toBeNull();
		expect(jobForPage(jobs, ['https://boards.greenhouse.io/harbour/jobs/999'])).toBeNull();
		expect(jobForPage(jobs, [undefined])).toBeNull();
	});
});

describe('suggestSource', () => {
	it('prefers the CV tailored for the job on the page', () => {
		const suggestion = suggestSource(
			session(),
			['https://boards.greenhouse.io/harbour/jobs/4012345'],
			{ kind: 'profile', id: 'p-backend' }
		);

		expect(suggestion).toMatchObject({
			source: { kind: 'document', id: 'd-harbour' },
			reason: 'job'
		});
	});

	it('then the last choice, then the default profile', () => {
		const elsewhere = ['https://example.com/apply'];
		expect(suggestSource(session(), elsewhere, { kind: 'profile', id: 'p-backend' })?.reason).toBe(
			'chosen'
		);
		expect(suggestSource(session(), elsewhere, { kind: 'profile', id: 'deleted' })).toMatchObject({
			source: { kind: 'profile', id: 'p-data' },
			reason: 'default'
		});
		expect(suggestSource(session({ profiles: [] }), elsewhere, null)?.source).toEqual({
			kind: 'document',
			id: 'd-harbour'
		});
		expect(suggestSource(session({ profiles: [], documents: [] }), elsewhere, null)).toBeNull();
	});

	it('reports a saved job with no CV yet', () => {
		const suggestion = suggestSource(
			session(),
			['https://meridian.example.com/careers/analytics-engineer'],
			null
		);

		expect(suggestion).toMatchObject({ reason: 'default', job: { id: 'j-meridian' } });
	});
});

describe('sourceName', () => {
	it('names profiles and CVs for a sentence', () => {
		const s = session();
		expect(sourceName(s, { kind: 'profile', id: 'p-data' })).toBe('Data engineering profile');
		expect(sourceName(s, { kind: 'document', id: 'd-harbour' })).toBe('Harbour Bank CV');
		expect(sourceName(s, { kind: 'document', id: 'd-plain' })).toBe('General CV');
	});
});
