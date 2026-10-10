import { act, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Toast from '#lib/components/ui/Toast.svelte';
import { INFO_TOAST_MS, toast } from '#lib/components/ui/toasts.svelte.ts';

describe('Toast', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		toast.clear();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders a polite notification region in the bottom right', () => {
		render(Toast);
		const region = screen.getByRole('region', { name: 'Notifications' });
		expect(region).toHaveAttribute('aria-live', 'polite');
		expect(region).toHaveClass('fixed', 'right-4', 'bottom-4');
	});

	it('shows info toasts as status and dismisses them after 4 seconds', async () => {
		render(Toast);
		await act(() => toast.info('CV duplicated.'));
		const item = screen.getByRole('status');
		expect(item).toHaveTextContent('CV duplicated.');
		expect(item).toHaveAttribute('data-kind', 'info');
		await act(() => vi.advanceTimersByTime(INFO_TOAST_MS - 1));
		expect(screen.queryByText('CV duplicated.')).not.toBeNull();
		await act(() => vi.advanceTimersByTime(1));
		expect(screen.queryByText('CV duplicated.')).toBeNull();
	});

	it('keeps error toasts until dismissed', async () => {
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
		render(Toast);
		await act(() => toast.error('Export failed. Try again.'));
		const item = screen.getByRole('alert');
		expect(item).toHaveClass('border-danger');
		expect(item.querySelector('[data-icon="placeholder-warning"]')).not.toBeNull();
		await act(() => vi.advanceTimersByTime(60_000));
		expect(screen.getByRole('alert')).toBeInTheDocument();
		await user.click(screen.getByRole('button', { name: 'Dismiss' }));
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('stacks several toasts in order', async () => {
		render(Toast);
		await act(() => {
			toast.info('First');
			toast.info('Second');
		});
		expect(screen.getAllByRole('status').map((el) => el.textContent?.trim())).toEqual([
			'First',
			'Second'
		]);
	});
});
