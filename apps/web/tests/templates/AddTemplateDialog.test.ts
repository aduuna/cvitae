import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AddTemplateDialog from '#lib/components/templates/AddTemplateDialog.svelte';
import { fakeApi, json } from '../extension/fake-api.ts';

const mocks = vi.hoisted(() => ({ session: null as never }));

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/paths', () => ({ resolve: (path: string) => path }));
vi.mock('#lib/auth/session.svelte.ts', async () => {
	const { sessionMock } = await import('../routes/session-mock');
	mocks.session = {
		...sessionMock(),
		aiModels: [{ id: 'claude-haiku', label: 'Claude Haiku', provider: 'claude', plan: 'free' }],
		billingEnabled: true
	} as never;
	return { session: mocks.session };
});

const DRAFT = {
	id: 'u-aaaaaaaaa2',
	name: 'Slate',
	description: 'Navy rules and tight spacing.',
	status: 'draft',
	paper_sizes: ['a4'],
	target_pages: 1,
	upload_id: null,
	created_at: '2026-11-07T10:00:00Z',
	updated_at: '2026-11-07T10:00:00Z',
	ai_model: 'claude-haiku',
	provider: 'claude',
	model: 'fake'
};
const PAGE = '<svg xmlns="http://www.w3.org/2000/svg" width="595pt" height="842pt"></svg>';
const PDF_UPLOAD = {
	id: 'up-1',
	filename: 'old-cv.pdf',
	mime_type: 'application/pdf',
	size_bytes: 2048,
	created_at: '2026-11-01T10:00:00Z'
};
const DOCX_UPLOAD = { ...PDF_UPLOAD, id: 'up-2', filename: 'word-cv.docx', mime_type: 'docx' };

const meter = (message: string | null) => ({ used: 0, limit: 20, message });

type Session = { usage: unknown };

function pdf(name = 'cv.pdf') {
	const file = new File(['%PDF'], name, { type: 'application/pdf' });
	Object.defineProperty(file, 'size', { value: 2048 });
	return file;
}

async function chooseFile(file: File) {
	const input = screen.getByTestId('dropzone-input') as HTMLInputElement;
	Object.defineProperty(input, 'files', { value: [file], configurable: true });
	await fireEvent.change(input);
}

function setup(routes: Parameters<typeof fakeApi>[0] = {}) {
	const onsaved = vi.fn();
	const onclose = vi.fn();
	const api = fakeApi({
		'GET /api/v1/uploads': () => json([PDF_UPLOAD, DOCX_UPLOAD]),
		'POST /api/v1/templates/custom': () => json(DRAFT, 201),
		'GET /api/v1/templates/u-aaaaaaaaa2/preview': () => json({ pages: [PAGE], page_count: 1 }),
		...routes
	});
	render(AddTemplateDialog, { onsaved, onclose });
	return { api, onsaved, onclose };
}

/** Makes a draft from a chosen file and waits for the result. */
async function reachReview() {
	await chooseFile(pdf());
	await userEvent.click(screen.getByRole('button', { name: 'Make template' }));
	await screen.findByLabelText('Template name');
}

describe('the add your own template dialog', () => {
	beforeEach(() => {
		(mocks.session as Session).usage = null;
	});
	afterEach(() => vi.unstubAllGlobals());

	it('explains what happens before anything is uploaded', () => {
		setup();

		const dialog = screen.getByRole('dialog', { name: 'Add your own template' });
		expect(dialog).toHaveTextContent('Claude rebuilds how it looks as a template');
		expect(dialog).toHaveTextContent('The text of that CV is not copied into the template');
		expect(dialog).toHaveTextContent('takes a little of your AI usage and runs on Claude');
		expect(dialog).toHaveTextContent('up to 2 minutes');
		expect(screen.getByRole('group', { name: 'CV file' })).toHaveTextContent(
			'Drop a PDF file here'
		);
		expect(screen.getByRole('button', { name: 'Make template' })).toBeDisabled();
	});

	it('refuses a DOCX in the file chooser, with the reason', async () => {
		setup();

		await chooseFile(new File(['x'], 'cv.docx', { type: '' }));

		expect(screen.getByRole('alert')).toHaveTextContent('A DOCX does not keep how a CV looks');
		expect(screen.getByRole('button', { name: 'Make template' })).toBeDisabled();
	});

	it('offers earlier PDF uploads only, and makes a template from one', async () => {
		let sent = '';
		setup({
			'POST /api/v1/templates/custom': async (request) => {
				sent = await request.text();
				return json(DRAFT, 201);
			}
		});

		await userEvent.click(await screen.findByRole('button', { name: 'Use old-cv.pdf' }));

		expect(screen.queryByText('word-cv.docx')).toBeNull();
		await screen.findByLabelText('Template name');
		expect(sent).toContain('name="upload_id"');
		expect(sent).toContain('up-1');
		expect(sent).not.toContain('name="file"');
	});

	it('shows progress while Claude works, and cancel goes back to the file', async () => {
		let seen: AbortSignal | undefined;
		setup({
			'POST /api/v1/templates/custom': (request) => {
				seen = request.signal;
				return new Promise<Response>(() => {});
			}
		});
		await chooseFile(pdf());
		await userEvent.click(screen.getByRole('button', { name: 'Make template' }));

		expect(screen.getByRole('progressbar')).toBeVisible();
		expect(screen.getByText("Reading your CV's design")).toBeVisible();
		expect(screen.getByText(/Working with Claude\. This can take 1 to 2 minutes\./)).toBeVisible();

		await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

		expect(screen.queryByRole('progressbar')).toBeNull();
		expect(screen.getByRole('button', { name: 'Make template' })).toBeEnabled();
		await waitFor(() => expect(seen?.aborted).toBe(true));
	});

	it('shows the draft with its preview and a name to keep', async () => {
		setup();

		await reachReview();

		const dialog = screen.getByRole('dialog', { name: 'Add your own template' });
		expect(dialog).toHaveTextContent('Made with Claude Haiku');
		expect(dialog).toHaveTextContent('Nothing is saved until you save the template');
		expect(screen.getByLabelText('Template name')).toHaveValue('Slate');
		expect(dialog).toHaveTextContent('Navy rules and tight spacing.');
		const preview = await screen.findByRole('img', { name: 'Preview of the new template' });
		expect(preview.getAttribute('src')).toContain('data:image/svg+xml');
		expect(screen.getByRole('button', { name: 'Discard' })).toBeVisible();
		expect(screen.getByRole('button', { name: 'Save template' })).toBeVisible();
	});

	it('saves under the name chosen and hands the preview to the page', async () => {
		let patched: unknown;
		const { onsaved, onclose } = setup({
			'PATCH /api/v1/templates/custom/u-aaaaaaaaa2': async (request) => {
				patched = await request.json();
				return json({ ...DRAFT, name: 'Slate navy', status: 'ready' });
			}
		});
		await reachReview();
		await screen.findByRole('img', { name: 'Preview of the new template' });

		await userEvent.clear(screen.getByLabelText('Template name'));
		await userEvent.type(screen.getByLabelText('Template name'), '  Slate navy ');
		await userEvent.click(screen.getByRole('button', { name: 'Save template' }));

		await waitFor(() => expect(onclose).toHaveBeenCalledOnce());
		expect(patched).toEqual({ name: 'Slate navy', status: 'ready' });
		expect(onsaved).toHaveBeenCalledWith(expect.objectContaining({ name: 'Slate navy' }), PAGE);
	});

	it('needs a name to save', async () => {
		setup();
		await reachReview();

		await userEvent.clear(screen.getByLabelText('Template name'));

		expect(screen.getByRole('button', { name: 'Save template' })).toBeDisabled();
		expect(screen.getByText('Give the template a name.')).toBeVisible();
	});

	it('deletes the draft when discarded', async () => {
		const deleted = vi.fn();
		const { onclose, onsaved } = setup({
			'DELETE /api/v1/templates/custom/u-aaaaaaaaa2': () => {
				deleted();
				return new Response(null, { status: 204 });
			}
		});
		await reachReview();

		await userEvent.click(screen.getByRole('button', { name: 'Discard' }));

		await waitFor(() => expect(onclose).toHaveBeenCalledOnce());
		expect(deleted).toHaveBeenCalledOnce();
		expect(onsaved).not.toHaveBeenCalled();
	});

	it('asks before a draft is lost to Escape, and keeps it on request', async () => {
		const { onclose } = setup();
		await reachReview();

		await userEvent.keyboard('{Escape}');

		const confirm = await screen.findByRole('dialog', { name: 'Discard this template?' });
		expect(confirm).toHaveTextContent('making another takes more of your AI usage');
		expect(onclose).not.toHaveBeenCalled();

		await userEvent.click(screen.getByRole('button', { name: 'Keep reviewing' }));

		expect(screen.queryByRole('dialog', { name: 'Discard this template?' })).toBeNull();
		expect(screen.getByLabelText('Template name')).toBeVisible();
		expect(onclose).not.toHaveBeenCalled();
	});

	it('closes without asking when there is no draft', async () => {
		const { onclose } = setup();

		await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

		expect(onclose).toHaveBeenCalledOnce();
	});

	it('shows a limit with the way to Pro, and any other failure as a message', async () => {
		(mocks.session as Session).usage = {
			plan: 'free',
			subscription: null,
			ai_runs: meter(null),
			templates: meter(null)
		};
		let answer = () =>
			json(
				{
					error: {
						code: 'quota_exceeded',
						message:
							"You have used all of this month's AI usage. Upgrade to Pro for 7 times as much.",
						details: { resource: 'ai_runs' }
					}
				},
				402
			);
		setup({ 'POST /api/v1/templates/custom': () => answer() });
		await chooseFile(pdf());

		await userEvent.click(screen.getByRole('button', { name: 'Make template' }));

		expect(await screen.findByRole('status')).toHaveTextContent('You have used all of this month');
		expect(screen.getByRole('button', { name: 'See plans' })).toBeVisible();

		answer = () =>
			json(
				{
					error: {
						code: 'template_failed',
						message: 'We could not turn this CV into a template. Try a PDF with a simpler layout.',
						details: { issues: ['compile_error'] }
					}
				},
				422
			);
		await userEvent.click(screen.getByRole('button', { name: 'Make template' }));

		expect(await screen.findByRole('alert')).toHaveTextContent('Try a PDF with a simpler layout');
		expect(screen.queryByRole('button', { name: 'See plans' })).toBeNull();
	});

	it('disables making a template when the usage already says there is no room', () => {
		(mocks.session as Session).usage = {
			plan: 'free',
			subscription: null,
			ai_runs: meter(null),
			templates: { used: 1, limit: 1, message: 'You have 1 custom template, the most on Free.' }
		};
		setup();

		expect(screen.getByRole('status')).toHaveTextContent('You have 1 custom template');
		expect(screen.getByRole('button', { name: 'Make template' })).toBeDisabled();
	});

	it('says so when saving finds no room, and keeps the draft', async () => {
		const { onclose } = setup({
			'PATCH /api/v1/templates/custom/u-aaaaaaaaa2': () =>
				json(
					{
						error: {
							code: 'quota_exceeded',
							message: 'You have 1 custom template, the most on Free.',
							details: { resource: 'templates' }
						}
					},
					402
				)
		});
		await reachReview();

		await userEvent.click(screen.getByRole('button', { name: 'Save template' }));

		expect(await screen.findByText('You have 1 custom template, the most on Free.')).toBeVisible();
		expect(onclose).not.toHaveBeenCalled();
		expect(screen.getByRole('button', { name: 'Save template' })).toBeEnabled();
	});
});
