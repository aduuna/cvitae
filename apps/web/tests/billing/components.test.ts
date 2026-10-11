import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import LimitNotice from '#lib/components/billing/LimitNotice.svelte';
import UsageMeter from '#lib/components/billing/UsageMeter.svelte';

const mocks = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$app/paths', () => ({ resolve: (path: string) => path }));

describe('LimitNotice', () => {
	it('shows why the action is blocked and the way to Pro', async () => {
		render(LimitNotice, {
			message: 'You have used all 5 AI runs this month. Upgrade to Pro for 150.',
			upgrade: true
		});

		expect(screen.getByRole('status')).toHaveTextContent(
			'You have used all 5 AI runs this month. Upgrade to Pro for 150.'
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
		render(UsageMeter, {
			label: 'AI runs this month',
			used: 3,
			limit: 5,
			caption: 'Resets on 1 November.'
		});

		const meter = screen.getByRole('meter', { name: 'AI runs this month' });
		expect(meter).toHaveAttribute('aria-valuenow', '3');
		expect(meter).toHaveAttribute('aria-valuemax', '5');
		expect(meter.firstElementChild).toHaveStyle({ width: '60%' });
		expect(screen.getByText('3 of 5')).toBeVisible();
		expect(screen.getByText('Resets on 1 November.')).toBeVisible();
	});

	it('stays full when a downgrade leaves more than the limit', () => {
		render(UsageMeter, { label: 'CVs', used: 7, limit: 3 });

		const meter = screen.getByRole('meter', { name: 'CVs' });
		expect(meter).toHaveAttribute('aria-valuenow', '3');
		expect(meter).toHaveAttribute('aria-valuetext', '7 of 3');
		expect(meter.firstElementChild).toHaveStyle({ width: '100%' });
	});
});
