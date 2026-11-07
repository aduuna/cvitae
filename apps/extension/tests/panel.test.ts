import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/sidepanel/App.svelte';
import { Panel } from '../src/sidepanel/panel.svelte.ts';
import { installChrome, type FakeChrome } from './chrome.ts';
import { loadFixture, sampleData } from './helpers.ts';

const JOB_PAGE = 'https://job-boards.greenhouse.io/harbour/jobs/4012345';
const at = '2026-10-01T09:00:00Z';

const session = {
	email: 'ada@example.com',
	display_name: null,
	profiles: [{ id: 'p1', name: 'Data engineering', is_default: true, updated_at: at }],
	documents: [{ id: 'd1', name: 'Harbour Bank CV', job_id: null, placeholders: 1, updated_at: at }],
	jobs: [] as unknown[]
};

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

type Route = (request: Request) => Response | Promise<Response>;

function fakeApi(routes: Record<string, Route>) {
	const calls: string[] = [];
	vi.stubGlobal(
		'fetch',
		vi.fn(async (input: Request) => {
			const key = `${input.method} ${new URL(input.url).pathname}`;
			calls.push(key);
			return routes[key]?.(input) ?? json({ error: { code: 'not_found', message: key } }, 404);
		})
	);
	return calls;
}

/** executeScript runs the function against this document, where the real content script runs. */
function runScriptsHere(fake: FakeChrome) {
	fake.chrome.scripting.executeScript.mockImplementation(async (injection: unknown) => {
		const { func, args = [] } = injection as {
			func?: (...a: unknown[]) => unknown;
			args?: unknown[];
		};
		return [{ frameId: 0, result: func ? await func(...args) : undefined }];
	});
}

beforeAll(async () => {
	// The content script, as the panel injects it: quiet, no prompt of its own.
	globalThis.__cvitaeQuiet = true;
	await import('../src/content/index.ts');
});

describe('side panel', () => {
	let fake: FakeChrome;

	beforeEach(() => {
		fake = installChrome({ id: 7, url: JOB_PAGE, windowId: 1 });
		runScriptsHere(fake);
	});

	it('asks to connect when there is no token', async () => {
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Connect' }));

		expect(fake.chrome.tabs.create).toHaveBeenCalledWith({
			url: 'http://localhost:5173/app/extension'
		});
	});

	it('reviews and fills a form', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		const calls = fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'GET /api/v1/extension/profiles/p1/application': () => json(sampleData())
		});
		loadFixture('greenhouse-new');
		render(App, { panel: new Panel() });

		expect(await screen.findByText('Your default profile.')).toBeVisible();
		expect(screen.getByRole('combobox', { name: 'Fill from' })).toHaveValue('profile:p1');
		expect(screen.getByText(/Greenhouse form on job-boards.greenhouse.io/)).toBeVisible();

		await userEvent.click(screen.getByRole('button', { name: 'Fill form' }));
		const role = (await screen.findByText('Role 1: Northwind Consulting')).closest('section')!;
		expect(within(role).getByText('March')).toBeVisible();
		// Leave the phone out, and change the first name before it is written.
		await userEvent.click(screen.getByRole('checkbox', { name: 'Phone' }));
		const first = screen.getByRole('textbox', { name: 'Text for First Name' });
		await userEvent.clear(first);
		await userEvent.type(first, 'Ama A.');
		await userEvent.click(screen.getByRole('button', { name: 'Fill 15 fields' }));

		expect(await screen.findByText(/Filled 15 fields/)).toBeVisible();
		expect(document.querySelector<HTMLInputElement>('#first_name')!.value).toBe('Ama A.');
		expect(document.querySelector<HTMLInputElement>('#phone')!.value).toBe('');
		expect(document.querySelector<HTMLSelectElement>('#start-date-month-0')!.value).toBe('3');
		expect(document.querySelector<HTMLInputElement>('#current-role-0')!.checked).toBe(true);
		expect(calls).toEqual([
			'GET /api/v1/extension/session',
			'GET /api/v1/extension/profiles/p1/application'
		]);

		await userEvent.click(screen.getByRole('button', { name: 'Undo fill' }));
		expect(document.querySelector<HTMLInputElement>('#first_name')!.value).toBe('');
	});

	it('picks up a CV tailored in the app when the user comes back to the application', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		const job = {
			id: 'j1',
			title: 'Data engineer',
			company: 'Harbour Bank',
			url: JOB_PAGE,
			created_at: at,
			updated_at: at
		};
		let current: unknown = { ...session, jobs: [job] };
		const calls = fakeApi({ 'GET /api/v1/extension/session': () => json(current) });
		const now = vi.spyOn(Date, 'now').mockReturnValue(1_000_000);
		render(App, { panel: new Panel() });
		expect(await screen.findByText('Your default profile.')).toBeVisible();

		// Meanwhile the user tailored a CV for this job, and switches back to this tab.
		current = {
			...session,
			jobs: [job],
			documents: [{ ...session.documents[0], job_id: 'j1' }]
		};
		now.mockReturnValue(1_000_000 + 31_000);
		fake.chrome.tabs.onActivated.emit({ tabId: 7 });

		expect(
			await screen.findByText('The CV you tailored for Data engineer at Harbour Bank.')
		).toBeVisible();
		expect(calls.filter((c) => c === 'GET /api/v1/extension/session')).toHaveLength(2);
		now.mockRestore();
	});

	it('says when nothing on the page matches', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'GET /api/v1/extension/profiles/p1/application': () => json(sampleData())
		});
		document.body.innerHTML = '<p>No form here.</p>';
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Fill form' }));

		expect(await screen.findByText(/No fields on this page match your profile/)).toBeVisible();
	});

	it('keeps a CV with placeholders from being attached', async () => {
		await fake.chrome.storage.local.set({
			token: 'cvx_good',
			source: { kind: 'document', id: 'd1' }
		});
		fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'GET /api/v1/extension/documents/d1/application': () => json(sampleData()),
			'GET /api/v1/extension/documents/d1/cv.pdf': () =>
				json(
					{
						error: {
							code: 'conflict',
							message: 'This CV still has 1 placeholder.',
							details: { placeholders: [{ text: 'number of analysts', bullet_id: 'b' }] }
						}
					},
					409
				)
		});
		loadFixture('lever');
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Fill form' }));
		await userEvent.click(await screen.findByRole('button', { name: 'Attach CV' }));

		expect(await screen.findByRole('alert')).toHaveTextContent(
			'This CV still has 1 placeholder. Fill them in the editor before you send it.'
		);
		await userEvent.click(screen.getByRole('button', { name: 'Open in editor' }));
		expect(fake.chrome.tabs.create).toHaveBeenCalledWith({
			url: 'http://localhost:5173/app/documents/d1'
		});
	});

	it('saves the job ad and opens Tailor with it', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		let saved: unknown = null;
		fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'POST /api/v1/extension/jobs': async (request) => {
				saved = await request.json();
				return json(
					{
						job: {
							id: 'j9',
							title: 'Data engineer',
							company: 'Harbour',
							url: JOB_PAGE,
							created_at: at,
							updated_at: at
						},
						created: true
					},
					201
				);
			}
		});
		document.title = 'Jobs';
		document.body.innerHTML = '<main><h1>Data engineer</h1><p>Build pipelines on Spark.</p></main>';
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Save job ad' }));
		const company = await screen.findByRole('textbox', { name: 'Company' });
		await userEvent.type(company, 'Harbour');
		await userEvent.click(screen.getByRole('button', { name: 'Save job' }));

		expect(await screen.findByText('Saved to Tailor.')).toBeVisible();
		expect(saved).toMatchObject({
			title: 'Data engineer',
			company: 'Harbour',
			description: 'Data engineer\nBuild pipelines on Spark.'
		});
		await userEvent.click(screen.getByRole('button', { name: 'Tailor a CV' }));
		expect(fake.chrome.tabs.create).toHaveBeenCalledWith({
			url: 'http://localhost:5173/app/tailor?job=j9'
		});
	});

	it('explains how to give access to a page it cannot read', async () => {
		fake = installChrome({ id: 7, windowId: 1 });
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		fakeApi({ 'GET /api/v1/extension/session': () => json(session) });
		render(App, { panel: new Panel() });

		expect(
			await screen.findByText(/click the Chameleon vitae button in the browser's toolbar/)
		).toBeVisible();
		expect(screen.queryByRole('button', { name: 'Fill form' })).toBeNull();
	});

	it('offers to allow a site that is not a known job site', async () => {
		fake = installChrome({ id: 7, url: 'https://careers.example.com/apply', windowId: 1 });
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		fakeApi({ 'GET /api/v1/extension/session': () => json(session) });
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Allow on this site' }));

		expect(fake.chrome.permissions.request).toHaveBeenCalledWith({
			origins: ['https://careers.example.com/*']
		});
		expect(fake.chrome.scripting.registerContentScripts).toHaveBeenCalled();
		await vi.waitFor(() =>
			expect(screen.queryByRole('button', { name: 'Allow on this site' })).toBeNull()
		);
	});

	it('disconnects when the server no longer accepts the token', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_revoked' });
		fakeApi({
			'GET /api/v1/extension/session': () =>
				json({ error: { code: 'unauthorized', message: 'No longer connected.' } }, 401)
		});
		render(App, { panel: new Panel() });

		expect(await screen.findByRole('button', { name: 'Connect' })).toBeVisible();
		expect(fake.store['token']).toBeUndefined();
	});

	it('disconnects this browser on request', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good', email: 'ada@example.com' });
		const calls = fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'DELETE /api/v1/extension/session': () => new Response(null, { status: 204 })
		});
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Disconnect' }));

		expect(await screen.findByRole('button', { name: 'Connect' })).toBeVisible();
		expect(calls).toContain('DELETE /api/v1/extension/session');
	});

	it('shows details to copy into fields it cannot fill', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'GET /api/v1/extension/profiles/p1/application': () => json(sampleData())
		});
		const writeText = vi.fn(async () => {});
		Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Show details' }));
		const role = (await screen.findByText('Lead data engineer at Northwind Consulting')).closest(
			'section'
		)!;
		expect(within(role).getByText('Mar 2021 to present')).toBeVisible();
		await userEvent.click(within(role).getByRole('button', { name: 'Copy company' }));

		expect(writeText).toHaveBeenCalledWith('Northwind Consulting');
		expect(await screen.findByText('Company copied.')).toBeVisible();
	});

	it('says why details could not be loaded', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'GET /api/v1/extension/profiles/p1/application': () =>
				json({ error: { code: 'service_unavailable', message: 'Try again soon.' } }, 503)
		});
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Show details' }));

		expect(await screen.findByRole('alert')).toHaveTextContent('Try again soon.');
	});

	it('remembers whether to offer filling on job sites', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		fakeApi({ 'GET /api/v1/extension/session': () => json(session) });
		render(App, { panel: new Panel() });

		const offer = await screen.findByRole('checkbox', { name: 'Offer to fill on job sites' });
		expect(offer).toBeChecked();
		await userEvent.click(offer);

		await vi.waitFor(() => expect(fake.store['offer']).toBe(false));
	});
});

describe('answer questions', () => {
	let fake: FakeChrome;

	type Body = {
		source: unknown;
		job_id: string | null;
		job: { description: string } | null;
		questions: { id: string; text: string; max_words: number | null; previous: string | null }[];
	};

	/** The api's answer to each question, by the start of its text. */
	function answering(texts: Record<string, string>, bodies: Body[] = []): Route {
		return async (request) => {
			const body = (await request.json()) as Body;
			bodies.push(body);
			return json({
				answers: body.questions.map((q) => {
					const text = Object.entries(texts).find(([start]) => q.text.startsWith(start))?.[1];
					return {
						id: q.id,
						text: text ?? '',
						inferred: q.text.startsWith('Describe')
							? [{ skill: 'Databricks', based_on: ['Spark'] }]
							: [],
						placeholders: (text ?? '').includes('[[') ? 1 : 0,
						shortened: false
					};
				}),
				ai_model: 'mimo-flash',
				ai_model_label: 'MiMo Flash',
				model: 'mimo-v2.6-flash'
			});
		};
	}

	const DRAFTS = {
		Describe: 'At Northwind I moved [[how many]] Spark jobs to Databricks.',
		Why: 'Harbour Bank builds the platforms I like to work on.',
		Tell: ''
	};

	beforeEach(async () => {
		fake = installChrome({ id: 7, url: 'https://careers.example.com/apply', windowId: 1 });
		runScriptsHere(fake);
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
	});

	it('finds questions, drafts them in one request, and fills what the user approves', async () => {
		const bodies: Body[] = [];
		const calls = fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'POST /api/v1/extension/answers': answering(DRAFTS, bodies)
		});
		loadFixture('questions');
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Find questions' }));

		// The page asks applicants not to use AI: the notice comes before any drafting.
		expect(
			await screen.findByText('This application asks applicants not to use AI.')
		).toBeVisible();
		expect(
			screen.getByText(/^"Please write your answers yourself: applications that use AI/)
		).toBeVisible();
		expect(
			screen.getByText(/From your Data engineering profile and the job ad on this page/)
		).toBeVisible();
		expect(screen.getByRole('checkbox', { name: /Describe a time you used dbt/ })).toBeChecked();
		expect(screen.getByText('200 words')).toBeVisible();
		// The field that has a value is listed, unticked.
		expect(screen.getByRole('checkbox', { name: /How did you handle/ })).not.toBeChecked();
		expect(calls).toEqual(['GET /api/v1/extension/session']);

		await userEvent.click(screen.getByRole('button', { name: 'Draft 3 answers' }));

		const dbt = await screen.findByRole('textbox', { name: /Answer to Describe a time/ });
		expect(dbt).toHaveValue(DRAFTS.Describe);
		expect(screen.getByText('Mentions Databricks, from your Spark work.')).toBeVisible();
		expect(screen.getByText('10 of 200 words')).toBeVisible();
		expect(screen.getByText('Not drafted. Answer this one yourself.')).toBeVisible();
		expect(screen.getByText(/1 placeholder in square brackets/)).toBeVisible();
		expect(screen.getByText(/Drafted with MiMo Flash/)).toBeVisible();
		expect(calls).toEqual(['GET /api/v1/extension/session', 'POST /api/v1/extension/answers']);
		const [sent] = bodies;
		expect(sent?.source).toEqual({ kind: 'profile', id: 'p1' });
		expect(sent?.job_id).toBeNull();
		expect(sent?.job?.description).toMatch(/We build data platforms for banks/);
		expect(sent?.questions.map((q) => [q.text, q.max_words])).toEqual([
			['Describe a time you used dbt in production.\nPlease answer in 150 to 200 words.', 200],
			['Why do you want to work at Harbour Bank?', null],
			['Tell us about a project you are proud of', null]
		]);
		// Nothing goes into the page before Fill.
		expect(document.querySelector<HTMLTextAreaElement>('#q_dbt')!.value).toBe('');

		await userEvent.clear(dbt);
		await userEvent.type(dbt, 'At Northwind I moved 40 Spark jobs to Databricks.');
		await userEvent.click(screen.getByRole('checkbox', { name: /Why do you want to work/ }));
		await userEvent.click(screen.getByRole('button', { name: 'Fill 1 answer' }));

		expect(await screen.findByText(/Filled 1 answer/)).toBeVisible();
		expect(document.querySelector<HTMLTextAreaElement>('#q_dbt')!.value).toBe(
			'At Northwind I moved 40 Spark jobs to Databricks.'
		);
		expect(document.querySelector<HTMLInputElement>('#q_why')!.value).toBe('');

		await userEvent.click(screen.getByRole('button', { name: 'Undo' }));
		expect(document.querySelector<HTMLTextAreaElement>('#q_dbt')!.value).toBe('');
		expect(await screen.findByText('Put back 1 field.')).toBeVisible();
		// Back to the drafts, as they were.
		expect(screen.getByRole('textbox', { name: /Answer to Describe a time/ })).toHaveValue(
			'At Northwind I moved 40 Spark jobs to Databricks.'
		);
	});

	it('redrafts one answer, sending the draft it replaces', async () => {
		const bodies: Body[] = [];
		fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'POST /api/v1/extension/answers': answering(DRAFTS, bodies)
		});
		loadFixture('questions');
		render(App, { panel: new Panel() });
		await userEvent.click(await screen.findByRole('button', { name: 'Find questions' }));
		await userEvent.click(await screen.findByRole('button', { name: 'Draft 3 answers' }));
		await screen.findByRole('textbox', { name: /Answer to Describe a time/ });

		const [redraft] = screen.getAllByRole('button', { name: 'Redraft this answer' });
		await userEvent.click(redraft!);

		await vi.waitFor(() => expect(bodies).toHaveLength(2));
		expect(bodies[1]?.questions.map((q) => [q.text.split('\n')[0], q.previous])).toEqual([
			['Describe a time you used dbt in production.', DRAFTS.Describe]
		]);
	});

	it('uses the saved job of the page, and lists questions when the form is filled', async () => {
		const bodies: Body[] = [];
		const job = {
			id: 'j1',
			title: 'Data engineer',
			company: 'Harbour Bank',
			url: 'https://careers.example.com/apply',
			created_at: at,
			updated_at: at
		};
		fakeApi({
			'GET /api/v1/extension/session': () => json({ ...session, jobs: [job] }),
			'GET /api/v1/extension/profiles/p1/application': () => json(sampleData()),
			'POST /api/v1/extension/answers': answering(DRAFTS, bodies)
		});
		loadFixture('questions');
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Fill form' }));

		expect(
			await screen.findByText(
				'From your Data engineering profile and the job ad you saved for Data engineer at Harbour Bank.'
			)
		).toBeVisible();
		await userEvent.click(screen.getByRole('button', { name: 'Draft 3 answers' }));
		await vi.waitFor(() => expect(bodies).toHaveLength(1));
		expect([bodies[0]?.job_id, bodies[0]?.job]).toEqual(['j1', null]);
	});

	it('shows why it could not draft, with a way to the plan', async () => {
		fakeApi({
			'GET /api/v1/extension/session': () => json(session),
			'POST /api/v1/extension/answers': () =>
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
		loadFixture('questions');
		render(App, { panel: new Panel() });
		await userEvent.click(await screen.findByRole('button', { name: 'Find questions' }));

		await userEvent.click(await screen.findByRole('button', { name: 'Draft 3 answers' }));

		expect(await screen.findByRole('alert')).toHaveTextContent(
			"You have used all of this month's AI usage."
		);
		await userEvent.click(screen.getByRole('button', { name: 'Open settings' }));
		expect(fake.chrome.tabs.create).toHaveBeenCalledWith({
			url: 'http://localhost:5173/app/settings'
		});
	});

	it('says when the page has no questions', async () => {
		fakeApi({ 'GET /api/v1/extension/session': () => json(session) });
		loadFixture('workday');
		render(App, { panel: new Panel() });

		await userEvent.click(await screen.findByRole('button', { name: 'Find questions' }));

		expect(await screen.findByText(/No open questions on this page/)).toBeVisible();
	});
});
