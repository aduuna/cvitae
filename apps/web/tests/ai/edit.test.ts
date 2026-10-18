import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AiEditChat, historyOf, scopeOptions, type ChatMessage } from '#lib/ai/edit.svelte.ts';
import AiEditPanel from '#lib/components/editor/AiEditPanel.svelte';
import { newSection } from '#lib/cv/factory.ts';
import type { CvContent } from '#lib/cv/types.ts';

const mocks = vi.hoisted(() => ({ session: null as never }));

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/paths', () => ({
	resolve: (path: string) => path,
	asset: (path: string) => path
}));
vi.mock('#lib/auth/session.svelte.ts', async () => {
	const { sessionMock } = await import('../routes/session-mock');
	mocks.session = {
		...sessionMock(),
		aiModels: [
			{ id: 'mimo-flash', label: 'MiMo Flash', provider: 'mimo', plan: 'free' },
			{ id: 'claude-sonnet', label: 'Claude Sonnet', provider: 'claude', plan: 'pro' }
		],
		defaultAiModel: 'mimo-flash',
		plansEnforced: true
	} as never;
	return { session: mocks.session };
});

function session() {
	return mocks.session as unknown as { usage: unknown; refreshUsage: () => Promise<unknown> };
}

function cv(summary = 'Data engineer with **9 years** of experience.'): CvContent {
	return {
		schema_version: 1,
		basics: { name: 'Ama', headline: '', email: '', phone: '', location: '', links: [] },
		summary,
		sections: [
			{ ...newSection('experience'), id: 'sec-exp' },
			{ ...newSection('skills'), id: 'sec-skills', title: ' ' }
		]
	};
}

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

function edited(content: CvContent, changed = true, reply = 'Shortened the summary.') {
	return { reply, content, changed, issues: [], ai_model: 'mimo-flash', model: 'mimo-v2.6-flash' };
}

/** An editor holding `initial`, recording what the chat saves and applies. */
function editor(initial: CvContent) {
	const state = { content: initial };
	return {
		state,
		content: () => state.content,
		save: vi.fn(async () => {}),
		apply: vi.fn((next: CvContent) => {
			state.content = next;
		})
	};
}

function assistant(chat: AiEditChat): Extract<ChatMessage, { role: 'assistant' }> {
	const message = chat.messages.findLast((m) => m.role === 'assistant');
	if (!message || message.role !== 'assistant') throw new Error('no reply');
	return message;
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('scopeOptions and historyOf', () => {
	it('lists the whole CV, the summary and each section', () => {
		expect(scopeOptions(cv())).toEqual([
			{ value: '', label: 'Whole CV' },
			{ value: 'summary', label: 'Summary' },
			{ value: 'sec-exp', label: 'Experience' },
			{ value: 'sec-skills', label: 'Untitled section' }
		]);
	});

	it('sends the latest twelve turns, without errors', () => {
		const messages: ChatMessage[] = Array.from({ length: 14 }, (_, id) => ({
			id,
			role: 'user',
			text: `Message ${id}`,
			scope: null
		}));
		messages.push({ id: 14, role: 'error', text: 'Failed.' });

		const history = historyOf(messages);

		expect(history).toHaveLength(12);
		expect(history[0]).toEqual({ role: 'user', text: 'Message 2' });
		expect(history.at(-1)).toEqual({ role: 'user', text: 'Message 13' });
	});
});

describe('AiEditChat', () => {
	it('saves the form, sends the request and puts the edit into the form', async () => {
		const form = editor(cv());
		const requests: Request[] = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (request: Request) => {
				requests.push(request);
				expect(form.save).toHaveBeenCalledOnce();
				return json(edited(cv('Data engineer.')));
			})
		);
		const chat = new AiEditChat('doc-1', form);

		const sent = await chat.send('  Shorten the summary ', { scope: 'summary', model: null });

		expect(sent).toBe(true);
		expect(requests[0]?.url).toMatch(/\/api\/v1\/documents\/doc-1\/ai-edit$/);
		expect(await requests[0]?.json()).toEqual({
			message: 'Shorten the summary',
			scope: 'summary',
			history: [],
			ai_model: null
		});
		expect(form.apply).toHaveBeenCalledWith(cv('Data engineer.'));
		expect(chat.messages.map((m) => m.role)).toEqual(['user', 'assistant']);
		const reply = assistant(chat);
		expect(reply.text).toBe('Shortened the summary.');
		expect(reply.edit?.status).toBe('applied');
		expect(chat.pending).toBe(false);

		expect(chat.canUndo(reply)).toBe(true);
		chat.undo(reply);
		expect(form.state.content).toEqual(cv());
		expect(reply.edit?.status).toBe('undone');
		expect(chat.canUndo(reply)).toBe(false);
	});

	it('sends the conversation so far with the next request', async () => {
		const bodies: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (request: Request) => {
				bodies.push(await request.json());
				return json(edited(cv(), false, 'It reads well.'));
			})
		);
		const chat = new AiEditChat('doc-1', editor(cv()));

		await chat.send('Is the summary clear?', { scope: null, model: 'mimo-flash' });
		await chat.send('Thanks', { scope: null, model: 'mimo-flash' });

		expect(bodies[1]).toMatchObject({
			history: [
				{ role: 'user', text: 'Is the summary clear?' },
				{ role: 'assistant', text: 'It reads well.' }
			]
		});
		expect(assistant(chat).edit).toBeNull();
	});

	it('holds an edit back when the form changed while it ran', async () => {
		const form = editor(cv());
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				form.state.content = cv('Typed meanwhile.');
				return json(edited(cv('Data engineer.')));
			})
		);
		const chat = new AiEditChat('doc-1', form);

		await chat.send('Shorten the summary', { scope: null, model: null });

		const reply = assistant(chat);
		expect(form.apply).not.toHaveBeenCalled();
		expect(reply.edit?.status).toBe('stale');
		expect(chat.canApply(reply)).toBe(true);

		chat.applyAnyway(reply);
		expect(form.state.content.summary).toBe('Data engineer.');
		chat.undo(reply);
		expect(form.state.content.summary).toBe('Typed meanwhile.');
	});

	it('offers no undo once the form changed after the edit', async () => {
		const form = editor(cv());
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => json(edited(cv('Data engineer.'))))
		);
		const chat = new AiEditChat('doc-1', form);

		await chat.send('Shorten the summary', { scope: null, model: null });
		form.state.content = cv('Edited by hand.');

		expect(chat.canUndo(assistant(chat))).toBe(false);
	});

	it('shows why a request failed or stopped', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () =>
				json(
					{ error: { code: 'quota_exceeded', message: 'You have used all of this month.' } },
					402
				)
			)
		);
		const chat = new AiEditChat('doc-1', editor(cv()));

		expect(await chat.send('Shorten', { scope: null, model: null })).toBe(false);
		expect(chat.messages.at(-1)).toMatchObject({
			role: 'error',
			text: 'You have used all of this month.'
		});

		vi.stubGlobal(
			'fetch',
			vi.fn(
				(request: Request) =>
					new Promise((_, reject) =>
						request.signal.addEventListener('abort', () =>
							reject(new DOMException('Aborted', 'AbortError'))
						)
					)
			)
		);
		const running = chat.send('Shorten', { scope: null, model: null });
		await waitFor(() => expect(fetch).toHaveBeenCalled());
		chat.stop();

		expect(await running).toBe(false);
		expect(chat.messages.at(-1)).toMatchObject({
			role: 'error',
			text: 'Stopped. Nothing was changed.'
		});
	});
});

describe('AiEditPanel', () => {
	beforeEach(() => {
		localStorage.clear();
		session().usage = null;
	});

	it('opens from its bar and remembers that it is open', async () => {
		const user = userEvent.setup();
		render(AiEditPanel, { chat: new AiEditChat('doc-1', editor(cv())), content: cv() });

		const bar = screen.getByRole('button', { name: 'Edit with AI' });
		expect(bar).toHaveAttribute('aria-expanded', 'false');
		expect(screen.queryByRole('textbox')).toBeNull();

		await user.click(bar);

		expect(screen.getByRole('button', { name: 'Edit with AI' })).toHaveAttribute(
			'aria-expanded',
			'true'
		);
		expect(screen.getByRole('textbox', { name: 'Change to make' })).toHaveFocus();
		expect(screen.getByText(/Ask for a change/)).toBeVisible();
		expect(localStorage.getItem('vitae.editor.aiPanel')).toBe('open');
	});

	it('sends with Enter, shows the reply and undoes the edit', async () => {
		localStorage.setItem('vitae.editor.aiPanel', 'open');
		const user = userEvent.setup();
		const form = editor(cv());
		const bodies: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (request: Request) => {
				bodies.push(await request.json());
				return json(edited(cv('Data engineer.')));
			})
		);
		render(AiEditPanel, { chat: new AiEditChat('doc-1', form), content: cv() });

		await user.selectOptions(screen.getByRole('combobox', { name: 'Part to change' }), 'summary');
		const input = screen.getByRole('textbox', { name: 'Change to make' });
		await user.type(input, 'Shorten the summary{Enter}');

		expect(await screen.findByText('Shortened the summary.')).toBeVisible();
		expect(bodies[0]).toMatchObject({ scope: 'summary', ai_model: 'mimo-flash' });
		expect(input).toHaveValue('');
		expect(screen.getByText('Summary', { selector: 'span' })).toBeVisible();
		expect(screen.getByText('Edited with MiMo Flash.')).toBeVisible();
		expect(session().refreshUsage).toHaveBeenCalled();

		await user.click(screen.getByRole('button', { name: 'Undo' }));
		expect(form.state.content.summary).toBe(cv().summary);
		expect(screen.getByText('Undone.')).toBeVisible();
	});

	it('gives the text back when the request fails', async () => {
		localStorage.setItem('vitae.editor.aiPanel', 'open');
		const user = userEvent.setup();
		vi.stubGlobal(
			'fetch',
			vi.fn(async () =>
				json({ error: { code: 'provider_error', message: 'MiMo could not finish.' } }, 502)
			)
		);
		render(AiEditPanel, { chat: new AiEditChat('doc-1', editor(cv())), content: cv() });

		const input = screen.getByRole('textbox', { name: 'Change to make' });
		await user.type(input, 'Shorten the summary');
		await user.click(screen.getByRole('button', { name: 'Send' }));

		expect(await screen.findByText('MiMo could not finish.')).toBeVisible();
		expect(input).toHaveValue('Shorten the summary');
	});

	it('stops at the AI usage limit', () => {
		localStorage.setItem('vitae.editor.aiPanel', 'open');
		session().usage = {
			ai_runs: { used: 20, limit: 20, message: "You have used all of this month's AI usage." }
		};
		render(AiEditPanel, { chat: new AiEditChat('doc-1', editor(cv())), content: cv() });

		expect(screen.getByRole('status')).toHaveTextContent(
			"You have used all of this month's AI usage."
		);
		expect(screen.getByRole('textbox', { name: 'Change to make' })).toBeDisabled();
		expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
	});
});
