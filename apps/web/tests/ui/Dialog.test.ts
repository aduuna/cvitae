import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { dialogSizes } from '#lib/components/ui/Dialog.svelte';
import DialogHarness from './harness/DialogHarness.svelte';

async function openDialog(props: { size?: 'sm' | 'md'; onclose?: () => void } = {}) {
	const user = userEvent.setup();
	render(DialogHarness, props);
	const opener = screen.getByRole('button', { name: 'Rename CV' });
	await user.click(opener);
	return { user, opener, dialog: screen.getByRole('dialog', { name: 'Rename CV' }) };
}

describe('Dialog', () => {
	it('is closed until opened', () => {
		render(DialogHarness);
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('opens as a labelled modal and focuses the first field', async () => {
		const { dialog } = await openDialog();
		expect(dialog).toHaveAttribute('aria-modal', 'true');
		expect(screen.getByLabelText('Name')).toHaveFocus();
		expect(dialog).toHaveClass(dialogSizes.sm);
	});

	it.each(Object.entries(dialogSizes))('supports the %s size', async (size, cls) => {
		const { dialog } = await openDialog({ size: size as 'sm' | 'md' });
		expect(dialog).toHaveClass(cls);
	});

	it('puts footer actions in order with the primary action last', async () => {
		const { dialog } = await openDialog();
		const footer = dialog.querySelector('footer');
		expect(
			Array.from(footer?.querySelectorAll('button') ?? []).map((b) => b.textContent?.trim())
		).toEqual(['Cancel', 'Save name']);
	});

	it('traps focus with Tab and Shift+Tab', async () => {
		const { user } = await openDialog();
		const close = screen.getByRole('button', { name: 'Close' });
		const save = screen.getByRole('button', { name: 'Save name' });
		await user.tab();
		await user.tab();
		expect(save).toHaveFocus();
		await user.tab();
		expect(close).toHaveFocus();
		await user.tab({ shift: true });
		expect(save).toHaveFocus();
	});

	it('closes with Escape and returns focus to the opener', async () => {
		const onclose = vi.fn();
		const { user, opener } = await openDialog({ onclose });
		await user.keyboard('{Escape}');
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(onclose).toHaveBeenCalledOnce();
		expect(opener).toHaveFocus();
	});

	it('closes with the close button', async () => {
		const { user } = await openDialog();
		await user.click(screen.getByRole('button', { name: 'Close' }));
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('closes when the backdrop is pressed, not the panel', async () => {
		const { dialog } = await openDialog();
		await fireEvent.pointerDown(dialog);
		expect(screen.getByRole('dialog')).toBeInTheDocument();
		await fireEvent.pointerDown(dialog.parentElement!);
		expect(screen.queryByRole('dialog')).toBeNull();
	});
});
