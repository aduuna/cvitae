import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';

const base = {
	open: true,
	title: 'Delete CV',
	message: 'This deletes the CV and its versions.',
	confirmLabel: 'Delete CV'
};

describe('ConfirmDialog', () => {
	it('shows the message with cancel first and the action last', () => {
		render(ConfirmDialog, { ...base, onconfirm: vi.fn() });
		const dialog = screen.getByRole('dialog', { name: 'Delete CV' });
		expect(dialog).toHaveTextContent('This deletes the CV and its versions.');
		const buttons = Array.from(dialog.querySelectorAll('footer button'));
		expect(buttons.map((b) => b.textContent?.trim())).toEqual(['Cancel', 'Delete CV']);
		expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
	});

	it('uses the danger variant for destructive actions', () => {
		render(ConfirmDialog, { ...base, danger: true, onconfirm: vi.fn() });
		const footer = screen.getByRole('dialog').querySelector('footer');
		expect(footer?.querySelector('button:last-child')).toHaveAttribute('data-variant', 'danger');
	});

	it('confirms and closes', async () => {
		const onconfirm = vi.fn();
		render(ConfirmDialog, { ...base, onconfirm });
		await userEvent.click(screen.getByRole('button', { name: 'Delete CV' }));
		expect(onconfirm).toHaveBeenCalledOnce();
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('cancels and closes', async () => {
		const onconfirm = vi.fn();
		const oncancel = vi.fn();
		render(ConfirmDialog, { ...base, onconfirm, oncancel });
		await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
		expect(oncancel).toHaveBeenCalledOnce();
		expect(onconfirm).not.toHaveBeenCalled();
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('shows a spinner while an async confirm runs', async () => {
		let finish: () => void = () => {};
		const onconfirm = vi.fn(() => new Promise<void>((resolve) => (finish = resolve)));
		render(ConfirmDialog, { ...base, onconfirm });
		const confirm = screen.getByRole('button', { name: 'Delete CV' });
		await userEvent.click(confirm);
		expect(confirm).toHaveAttribute('aria-busy', 'true');
		finish();
		await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
	});

	it('requires typed confirmation when confirmText is set', async () => {
		const user = userEvent.setup();
		const onconfirm = vi.fn();
		render(ConfirmDialog, {
			...base,
			title: 'Delete account',
			confirmLabel: 'Delete account',
			danger: true,
			confirmText: 'ada@example.com',
			onconfirm
		});
		const field = screen.getByLabelText('Type ada@example.com to confirm');
		const confirm = screen.getByRole('button', { name: 'Delete account' });
		expect(field).toHaveFocus();
		expect(confirm).toBeDisabled();
		await user.type(field, 'ada@example.co');
		expect(confirm).toBeDisabled();
		await user.type(field, 'm');
		expect(confirm).toBeEnabled();
		await user.keyboard('{Enter}');
		expect(onconfirm).toHaveBeenCalledOnce();
	});

	it('matches typed confirmation exactly unless told to ignore case', async () => {
		const user = userEvent.setup();
		render(ConfirmDialog, { ...base, confirmText: 'Ada@Example.com', onconfirm: vi.fn() });
		const confirm = screen.getByRole('button', { name: 'Delete CV' });

		await user.type(screen.getByLabelText('Type Ada@Example.com to confirm'), 'ada@example.com');

		expect(confirm).toBeDisabled();
	});

	it('ignores case and surrounding spaces when asked to, and passes on what was typed', async () => {
		const user = userEvent.setup();
		const onconfirm = vi.fn();
		render(ConfirmDialog, {
			...base,
			confirmText: 'Ada@Example.com',
			ignoreCase: true,
			onconfirm
		});
		const confirm = screen.getByRole('button', { name: 'Delete CV' });
		const field = screen.getByLabelText('Type Ada@Example.com to confirm');

		await user.type(field, '  ada@example.co');
		expect(confirm).toBeDisabled();
		await user.type(field, 'M  ');
		expect(confirm).toBeEnabled();
		await user.click(confirm);

		expect(onconfirm).toHaveBeenCalledExactlyOnceWith('ada@example.coM');
	});

	it('still refuses text that is a different address, whatever its case', async () => {
		const user = userEvent.setup();
		render(ConfirmDialog, {
			...base,
			confirmText: 'ada@example.com',
			ignoreCase: true,
			onconfirm: vi.fn()
		});

		await user.type(screen.getByLabelText('Type ada@example.com to confirm'), 'ADA@EXAMPLE.ORG');

		expect(screen.getByRole('button', { name: 'Delete CV' })).toBeDisabled();
	});

	it('passes an empty string without typed confirmation', async () => {
		const onconfirm = vi.fn();
		render(ConfirmDialog, { ...base, onconfirm });

		await userEvent.click(screen.getByRole('button', { name: 'Delete CV' }));

		expect(onconfirm).toHaveBeenCalledExactlyOnceWith('');
	});
});
