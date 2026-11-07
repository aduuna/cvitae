import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '#lib/api/client.ts';
import DataCard from '#lib/components/settings/DataCard.svelte';
import { toast } from '#lib/components/ui/toasts.svelte.ts';

const mocks = vi.hoisted(() => ({
	exportAccount: vi.fn(async () => {}),
	deleteAccount: vi.fn<(email: string) => Promise<void>>(async () => {})
}));
vi.mock('#lib/account.ts', () => mocks);

const EMAIL = 'ada@example.com';

function messages(kind: 'info' | 'error') {
	return toast.items.filter((item) => item.kind === kind).map((item) => item.message);
}

beforeEach(() => {
	mocks.exportAccount.mockReset();
	mocks.exportAccount.mockResolvedValue(undefined);
	mocks.deleteAccount.mockReset();
	mocks.deleteAccount.mockResolvedValue(undefined);
	toast.clear();
});
afterEach(() => toast.clear());

describe('DataCard', () => {
	it('offers the export and the deletion, each with what it does', () => {
		render(DataCard, { email: EMAIL, ondeleted: vi.fn() });

		expect(screen.getByRole('heading', { name: 'Data' })).toBeVisible();
		expect(screen.getByRole('button', { name: 'Export data' })).toBeEnabled();
		expect(screen.getByRole('button', { name: 'Delete account' })).toBeEnabled();
		expect(screen.getByText(/one JSON file/)).toBeVisible();
		expect(screen.getByText(/This cannot be undone/)).toBeVisible();
		expect(screen.getByText(/cancel your subscription first/)).toBeVisible();
	});

	it('exports and says so', async () => {
		render(DataCard, { email: EMAIL, ondeleted: vi.fn() });

		await userEvent.click(screen.getByRole('button', { name: 'Export data' }));

		expect(mocks.exportAccount).toHaveBeenCalledOnce();
		await vi.waitFor(() => expect(messages('info')).toEqual(['Your data was exported.']));
	});

	it('says why an export failed', async () => {
		mocks.exportAccount.mockRejectedValueOnce(
			new ApiError(0, 'network', 'Could not reach the server.')
		);
		render(DataCard, { email: EMAIL, ondeleted: vi.fn() });

		await userEvent.click(screen.getByRole('button', { name: 'Export data' }));

		await vi.waitFor(() => expect(messages('error')).toEqual(['Could not reach the server.']));
		expect(screen.getByRole('button', { name: 'Export data' })).toBeEnabled();
	});

	it('asks for the email before it deletes, with a danger button', async () => {
		const user = userEvent.setup();
		render(DataCard, { email: EMAIL, ondeleted: vi.fn() });

		await user.click(screen.getByRole('button', { name: 'Delete account' }));

		const dialog = screen.getByRole('dialog', { name: 'Delete account' });
		expect(dialog).toHaveTextContent('It cannot be undone.');
		const confirm = dialog.querySelector('footer button:last-child') as HTMLButtonElement;
		expect(confirm).toHaveTextContent('Delete account');
		expect(confirm).toHaveAttribute('data-variant', 'danger');
		expect(confirm).toBeDisabled();
		const field = screen.getByLabelText(`Type ${EMAIL} to confirm`);
		await user.type(field, 'ada@example.co');
		expect(confirm).toBeDisabled();
		await user.type(field, 'x');
		expect(confirm).toBeDisabled();
		await user.type(field, '{Backspace}m');
		expect(confirm).toBeEnabled();
		expect(mocks.deleteAccount).not.toHaveBeenCalled();
	});

	it('deletes with the typed email, says so and ends the session', async () => {
		const user = userEvent.setup();
		const ondeleted = vi.fn();
		render(DataCard, { email: EMAIL, ondeleted });

		await user.click(screen.getByRole('button', { name: 'Delete account' }));
		await user.type(screen.getByLabelText(`Type ${EMAIL} to confirm`), EMAIL);
		await user.keyboard('{Enter}');

		await vi.waitFor(() => expect(ondeleted).toHaveBeenCalledOnce());
		expect(mocks.deleteAccount).toHaveBeenCalledExactlyOnceWith(EMAIL);
		expect(messages('info')).toEqual(['Your account and everything in it was deleted.']);
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('cancelling deletes nothing', async () => {
		const user = userEvent.setup();
		const ondeleted = vi.fn();
		render(DataCard, { email: EMAIL, ondeleted });

		await user.click(screen.getByRole('button', { name: 'Delete account' }));
		await user.type(screen.getByLabelText(`Type ${EMAIL} to confirm`), EMAIL);
		await user.click(screen.getByRole('button', { name: 'Cancel' }));

		expect(mocks.deleteAccount).not.toHaveBeenCalled();
		expect(ondeleted).not.toHaveBeenCalled();
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('keeps the session and shows the reason when the account is not deleted', async () => {
		const user = userEvent.setup();
		const ondeleted = vi.fn();
		mocks.deleteAccount.mockRejectedValueOnce(
			new ApiError(409, 'conflict', 'Cancel your Pro subscription first.')
		);
		render(DataCard, { email: EMAIL, ondeleted });

		await user.click(screen.getByRole('button', { name: 'Delete account' }));
		await user.type(screen.getByLabelText(`Type ${EMAIL} to confirm`), EMAIL);
		await user.keyboard('{Enter}');

		await vi.waitFor(() =>
			expect(messages('error')).toEqual(['Cancel your Pro subscription first.'])
		);
		expect(ondeleted).not.toHaveBeenCalled();
		expect(messages('info')).toEqual([]);
	});
});
