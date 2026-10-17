import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import LimitNotice from '#lib/components/billing/LimitNotice.svelte';
import UsageMeter from '#lib/components/billing/UsageMeter.svelte';

const mocks = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$app/paths', () => ({
	resolve: (path: string) => path,
	asset: (path: string) => path
}));

describe('LimitNotice', () => {
	it('shows why the action is blocked and the way to Pro', async () => {
		render(LimitNotice, {
			message: "You have used all of this month's AI usage. Upgrade to Pro for 7 times as much.",
			upgrade: true
		});

		expect(screen.getByRole('status')).toHaveTextContent(
			"You have used all of this month's AI usage. Upgrade to Pro for 7 times as much."
		);
		await userEvent.click(screen.getByRole('button', { name: 'See plans' }));
		expect(mocks.goto).toHaveBeenCalledWith('/app/settings?tab=billing');
	});

	it('offers no upgrade when there is none to offer', () => {
		render(LimitNotice, { message: 'They reset on 1 November.' });

		expect(screen.queryByRole('button')).toBeNull();
	});
});

describe('UsageMeter', () => {
	it('shows used of limit as text and as a meter', () => {
		render(UsageMeter, { label: 'CVs', used: 3, limit: 5, caption: 'Delete one to make room.' });

		const meter = screen.getByRole('meter', { name: 'CVs' });
		expect(meter).toHaveAttribute('aria-valuenow', '3');
		expect(meter).toHaveAttribute('aria-valuemax', '5');
		expect(meter.firstElementChild).toHaveStyle({ width: '60%' });
		expect(screen.getByText('3 of 5')).toBeVisible();
		expect(screen.getByText('Delete one to make room.')).toBeVisible();
	});

	it('shows AI usage as a share, rounded down so 100% is the limit', () => {
		render(UsageMeter, { label: 'AI usage this month', used: 149, limit: 150, percent: true });

		const meter = screen.getByRole('meter', { name: 'AI usage this month' });
		expect(meter).toHaveAttribute('aria-valuenow', '99');
		expect(meter).toHaveAttribute('aria-valuemax', '100');
		expect(meter).toHaveAttribute('aria-valuetext', '99%');
		expect(screen.getByText('99%')).toBeVisible();
		expect(screen.queryByText(/149/)).toBeNull();
	});

	it('stays full when a downgrade leaves more than the limit', () => {
		render(UsageMeter, { label: 'CVs', used: 7, limit: 3 });

		const meter = screen.getByRole('meter', { name: 'CVs' });
		expect(meter).toHaveAttribute('aria-valuenow', '3');
		expect(meter).toHaveAttribute('aria-valuetext', '7 of 3');
		expect(meter.firstElementChild).toHaveStyle({ width: '100%' });
	});
});
