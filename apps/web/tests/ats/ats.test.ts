import { render, screen, waitFor, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { coverage, jobLabel, keywordGroups, titleLine } from '#lib/ats.ts';
import AtsDialog from '#lib/components/ats/AtsDialog.svelte';
import AtsReport from '#lib/components/ats/AtsReport.svelte';
import type { AtsKeyword, AtsReport as Report, DocumentAts } from '#lib/cv/types.ts';
import { fakeApi, json } from '../extension/fake-api.ts';

const mocks = vi.hoisted(() => ({ session: null as never }));

vi.mock('$app/paths', () => ({ resolve: (path: string) => path }));
vi.mock('#lib/auth/session.svelte.ts', async () => {
	const { sessionMock } = await import('../routes/session-mock');
	mocks.session = sessionMock() as never;
	return { session: mocks.session };
});

function keyword(term: string, overrides: Partial<AtsKeyword> = {}): AtsKeyword {
	return { term, importance: 'other', found_in: [], in_profile: null, ...overrides };
}

function report(overrides: Partial<Report> = {}): Report {
	return {
		score: 75,
		band: 'good',
		title: 'Data Engineer',
		title_found: true,
		keywords: [
			keyword('Python', { importance: 'required', found_in: ['experience', 'skills'] }),
			keyword('SQL', { importance: 'required', found_in: ['skills'] }),
			keyword('Kafka', { importance: 'preferred', in_profile: true }),
			keyword('Snowflake', { importance: 'preferred', in_profile: false })
		],
		checks: [
			{ id: 'contact', ok: true, message: 'Your email, phone and location are in the header.' },
			{ id: 'placeholders', ok: false, message: 'Fill in 1 placeholder.' }
		],
		...overrides
	};
}

const job = {
	id: 'j1',
	title: 'Data engineer',
	company: 'Agoda',
	url: null,
	created_at: '2026-10-20T09:00:00Z',
	updated_at: '2026-10-20T09:00:00Z'
};

describe('the ATS helpers', () => {
	it('groups keywords by what the person can do about them', () => {
		const groups = keywordGroups(
			report({ keywords: [...report().keywords, keyword('Rust', { in_profile: null })] })
		);

		expect(groups.found.map((k) => k.term)).toEqual(['Python', 'SQL']);
		expect(groups.leftOut.map((k) => k.term)).toEqual(['Kafka']);
		expect(groups.notInProfile.map((k) => k.term)).toEqual(['Snowflake']);
		expect(groups.notInCv.map((k) => k.term)).toEqual(['Rust']);
		expect(groups.skillsOnly.map((k) => k.term)).toEqual(['SQL']);
	});

	it('words the coverage, the title and the score', () => {
		expect(coverage(report())).toBe('2 of 4 job keywords are in this CV.');
		expect(coverage(report({ keywords: [keyword('Go')] }))).toBe(
			'0 of 1 job keyword is in this CV.'
		);
		expect(titleLine(report())).toBe('Your headline or a role says "Data Engineer".');
		expect(titleLine(report({ title_found: false }))).toMatch(/do not say "Data Engineer"/);
		expect(titleLine(report({ title: '' }))).toBeNull();
		expect(jobLabel(job)).toBe('Data engineer at Agoda');
		expect(jobLabel({ title: '', company: '' })).toBe('Untitled job');
	});
});

describe('AtsReport', () => {
	it('shows the score, the keyword groups and the checks', () => {
		render(AtsReport, { report: report(), level: 3 });

		expect(screen.getByText('Good match')).toBeVisible();
		const meter = screen.getByRole('meter', { name: 'ATS score' });
		expect(meter).toHaveAttribute('aria-valuenow', '75');
		expect(meter).toHaveAttribute('aria-valuetext', '75 of 100, Good match');
		expect(screen.getByText(/2 of 4 job keywords are in this CV\./)).toBeVisible();
		expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent?.trim())).toEqual([
			'Left out of this CV (1)',
			'Not in your profile (1)',
			'In this CV (2)',
			'Readability'
		]);
		expect(screen.getByText(/Only in your skills list: SQL\./)).toBeVisible();
		const inCv = within(screen.getByRole('list', { name: 'In this CV' }));
		expect(inCv.getByText('Python')).toHaveClass('font-medium');
		expect(inCv.getAllByText('(must-have)', { exact: false })[0]).toHaveClass('sr-only');
		expect(screen.getByText('Keywords in bold are must-haves in the job ad.')).toBeVisible();
		expect(screen.getByText('To fix:', { exact: false }).parentElement).toHaveTextContent(
			'To fix: Fill in 1 placeholder.'
		);
	});

	it('can leave the checks out, and says when there is nothing to match', () => {
		render(AtsReport, {
			report: report({ score: null, band: null, keywords: [] }),
			checks: false
		});

		expect(screen.getByText('This job ad names no keywords to match.')).toBeVisible();
		expect(screen.queryByRole('meter')).toBeNull();
		expect(screen.queryByText('Readability')).toBeNull();
		expect(screen.queryByText(/must-haves/)).toBeNull();
	});
});

describe('AtsDialog', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	function open(ats: DocumentAts | null, onchange = vi.fn(async () => {})) {
		render(AtsDialog, { open: true, documentId: 'd1', ats, onchange });
		return onchange;
	}

	it('links a saved job to a CV that has none', async () => {
		const api = fakeApi({
			'GET /api/v1/jobs': () => json([job, { ...job, id: 'j2', title: 'Analytics engineer' }]),
			'PATCH /api/v1/documents/d1': () => json({ id: 'd1', job_id: 'j2' })
		});
		const onchange = open({ job: null, report: null });

		const select = await screen.findByRole('combobox', { name: 'Job' });
		await userEvent.selectOptions(select, 'j2');
		await userEvent.click(screen.getByRole('button', { name: 'Check against this job' }));

		await waitFor(() => expect(onchange).toHaveBeenCalled());
		const patch = api.fetch.mock.calls
			.map(([request]) => request as Request)
			.find((request) => request.method === 'PATCH');
		expect(await patch?.json()).toEqual({ job_id: 'j2' });
	});

	it('points to Tailor when there are no saved jobs', async () => {
		fakeApi({ 'GET /api/v1/jobs': () => json([]) });
		open({ job: null, report: null });

		expect(await screen.findByText(/No saved jobs yet/)).toBeVisible();
		expect(screen.getByRole('link', { name: 'Go to Tailor' })).toHaveAttribute(
			'href',
			'/app/tailor'
		);
	});

	it('reads a job ad once before scoring, and counts it as AI usage', async () => {
		const api = fakeApi({
			'POST /api/v1/jobs/j1/analyze': () => json({ ...job, description: 'Ad', analysis: {} })
		});
		const onchange = open({ job, report: null });

		expect(screen.getByText(/Data engineer at Agoda has not been read yet/)).toBeVisible();
		await userEvent.click(screen.getByRole('button', { name: 'Read the job ad' }));

		await waitFor(() => expect(onchange).toHaveBeenCalled());
		expect(api.calls).toEqual(['POST /api/v1/jobs/j1/analyze']);
		expect(
			(mocks.session as unknown as { refreshUsage: () => unknown }).refreshUsage
		).toHaveBeenCalled();
	});

	it('says why a job ad could not be read', async () => {
		fakeApi({
			'POST /api/v1/jobs/j1/analyze': () =>
				json(
					{
						error: {
							code: 'quota_exceeded',
							message: "You have used all of this month's AI usage.",
							details: { resource: 'ai_runs' }
						}
					},
					402
				)
		});
		const onchange = open({ job, report: null });

		await userEvent.click(screen.getByRole('button', { name: 'Read the job ad' }));

		expect(await screen.findByRole('alert')).toHaveTextContent(
			"You have used all of this month's AI usage."
		);
		expect(onchange).not.toHaveBeenCalled();
	});

	it('shows the report for the linked job, and lets the job change', async () => {
		fakeApi({ 'GET /api/v1/jobs': () => json([job]) });
		open({ job, report: report() });

		expect(screen.getByText('For Data engineer at Agoda')).toBeVisible();
		expect(screen.getByRole('meter', { name: 'ATS score' })).toBeVisible();

		await userEvent.click(screen.getByRole('button', { name: 'Change job' }));
		expect(await screen.findByRole('combobox', { name: 'Job' })).toHaveValue('j1');
		await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
		expect(screen.getByRole('meter', { name: 'ATS score' })).toBeVisible();
	});
});
