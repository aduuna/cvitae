import { act, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TooltipHarness from './harness/TooltipHarness.svelte';

describe('Tooltip', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	function setup(props: { describe?: boolean; disabled?: boolean } = {}) {
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
		render(TooltipHarness, props);
		return { user, trigger: screen.getByRole('button', { name: 'Share' }) };
	}

	it('describes its trigger', () => {
		const { trigger } = setup();
		const tip = screen.getByRole('tooltip');
		expect(trigger).toHaveAttribute('aria-describedby', tip.id);
		expect(tip).toHaveTextContent('Copy link');
		expect(tip).toHaveAttribute('data-state', 'closed');
	});

	it('appears after a 400ms hover delay and hides on leave', async () => {
		const { user, trigger } = setup();
		await user.hover(trigger);
		await act(() => vi.advanceTimersByTime(399));
		expect(screen.getByRole('tooltip')).toHaveAttribute('data-state', 'closed');
		await act(() => vi.advanceTimersByTime(1));
		expect(screen.getByRole('tooltip')).toHaveAttribute('data-state', 'open');
		expect(screen.getByRole('tooltip')).toHaveClass('bg-fg', 'text-surface', 'text-xs');
		await user.unhover(trigger);
		expect(screen.getByRole('tooltip')).toHaveAttribute('data-state', 'closed');
	});

	it('appears on keyboard focus and closes with Escape', async () => {
		const { user, trigger } = setup();
		await user.tab();
		expect(trigger).toHaveFocus();
		await act(() => vi.advanceTimersByTime(400));
		expect(screen.getByRole('tooltip')).toHaveAttribute('data-state', 'open');
		await user.keyboard('{Escape}');
		expect(screen.getByRole('tooltip')).toHaveAttribute('data-state', 'closed');
	});

	it('does nothing when disabled', async () => {
		const { user, trigger } = setup({ disabled: true });
		expect(trigger).not.toHaveAttribute('aria-describedby');
		await user.hover(trigger);
		await act(() => vi.advanceTimersByTime(400));
		expect(screen.queryByText('Copy link')).toBeNull();
	});
});
