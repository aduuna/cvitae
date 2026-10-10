import { act, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import IconButton, { iconButtonVariants } from '#lib/components/ui/IconButton.svelte';

describe('IconButton', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it('uses the label as its accessible name', () => {
		render(IconButton, { label: 'Delete CV', icon: 'delete' });
		const button = screen.getByRole('button', { name: 'Delete CV' });
		expect(button.querySelector('[data-icon="delete"]')).not.toBeNull();
	});

	it.each(Object.entries(iconButtonVariants))('applies the %s variant', (variant, classes) => {
		render(IconButton, {
			label: 'Copy',
			icon: 'duplicate',
			variant: variant as keyof typeof iconButtonVariants
		});
		expect(screen.getByRole('button')).toHaveClass(...classes.split(' '));
	});

	it('is square at 28px and 32px', () => {
		const { unmount } = render(IconButton, { label: 'Copy', icon: 'duplicate', size: 'sm' });
		expect(screen.getByRole('button')).toHaveClass('size-7');
		unmount();
		render(IconButton, { label: 'Copy', icon: 'duplicate' });
		expect(screen.getByRole('button')).toHaveClass('size-8');
	});

	it('shows the label as a tooltip on hover without duplicating it for screen readers', async () => {
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
		render(IconButton, { label: 'Delete CV', icon: 'delete' });
		const button = screen.getByRole('button', { name: 'Delete CV' });
		expect(button).not.toHaveAttribute('aria-describedby');
		await user.hover(button);
		await act(() => vi.advanceTimersByTime(400));
		const tip = screen.getByText('Delete CV');
		expect(tip).toHaveAttribute('aria-hidden', 'true');
		expect(tip).toHaveAttribute('data-state', 'open');
	});

	it('fires onclick from mouse and keyboard', async () => {
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
		const onclick = vi.fn();
		render(IconButton, { label: 'Close', icon: 'close', onclick });
		await user.click(screen.getByRole('button'));
		await user.keyboard('{Enter}');
		expect(onclick).toHaveBeenCalledTimes(2);
	});
});
