import { describe, expect, it, vi } from 'vitest';
import { showPrompt, type PromptActions } from '../src/content/prompt.ts';

function setup(overrides: Partial<PromptActions> = {}, trusted = true) {
	const actions: PromptActions = {
		source: 'Data engineering profile',
		fill: vi.fn(async () => ({ ok: true as const, count: 6 })),
		undo: vi.fn(() => 6),
		close: vi.fn(),
		...overrides
	};
	const remove = showPrompt(actions, document, () => trusted);
	const root = document.querySelector('cvitae-prompt')!.shadowRoot!;
	const button = (label: string) =>
		[...root.querySelectorAll('button')].find((b) => b.textContent === label);
	const text = () => root.querySelector('.text')?.textContent;
	return { actions, remove, root, button, text };
}

describe('the fill prompt', () => {
	it('offers to fill from the chosen source', () => {
		const { text, button, root } = setup();

		expect(text()).toBe(
			'Fill this application from your Data engineering profile? Nothing is sent until you submit it yourself.'
		);
		expect(button('Fill fields')).toBeDefined();
		expect(root.querySelector('section')).toHaveAttribute('aria-label', 'Chameleon vitae');
	});

	it('fills, reports, and undoes', async () => {
		const { actions, button, text } = setup();

		button('Fill fields')!.click();
		await vi.waitFor(() =>
			expect(text()).toBe('Filled 6 fields. Check each one before you submit.')
		);
		button('Undo fill')!.click();

		expect(actions.undo).toHaveBeenCalledOnce();
		expect(text()).toBe('Put back 6 fields.');
		expect(button('Undo fill')!.disabled).toBe(true);
	});

	it('shows why a fill failed and lets the user try again', async () => {
		const { button, text } = setup({
			fill: vi.fn(async () => ({ ok: false as const, message: 'Could not reach the server.' }))
		});

		button('Fill fields')!.click();

		await vi.waitFor(() => expect(text()).toBe('Could not reach the server.'));
		expect(button('Fill fields')!.disabled).toBe(false);
	});

	it('closes', () => {
		const { actions, button } = setup();

		button('Close')!.click();

		expect(document.querySelector('cvitae-prompt')).toBeNull();
		expect(actions.close).toHaveBeenCalledOnce();
	});

	it('ignores clicks a page script makes', () => {
		const { actions, button } = setup({}, false);

		button('Fill fields')!.click();
		button('Close')!.click();

		expect(actions.fill).not.toHaveBeenCalled();
		expect(document.querySelector('cvitae-prompt')).not.toBeNull();
	});
});
