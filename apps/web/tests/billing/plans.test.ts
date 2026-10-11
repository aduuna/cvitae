import { describe, expect, it } from 'vitest';
import {
	blockedReason,
	canUpgrade,
	formatDay,
	limitReached,
	paystackReference,
	planSummary,
	runsLabel,
	subscriptionStatus,
	type Usage
} from '#lib/billing/plans.ts';

function usage(overrides: Partial<Usage> = {}): Usage {
	return {
		plan: 'free',
		period_start: '2026-10-01T00:00:00Z',
		period_end: '2026-11-01T00:00:00Z',
		ai_runs: { used: 3, limit: 5, message: null },
		documents: { used: 1, limit: 3, message: null },
		profiles: { used: 1, limit: 1, message: 'You have 1 profile, the most on Free.' },
		subscription: null,
		...overrides
	};
}

function subscribed(
	status: NonNullable<Usage['subscription']>['status'],
	plan: Usage['plan'] = 'pro',
	current_period_end: string | null = '2026-11-10T00:00:00Z'
): Usage {
	return usage({ plan, subscription: { status, current_period_end, manageable: true } });
}

describe('billing helpers', () => {
	it('labels usage and plans with digits and units', () => {
		expect(runsLabel({ used: 3, limit: 5, message: null })).toBe('3 of 5 AI runs');
		expect(runsLabel({ used: 1200, limit: 1500, message: null })).toBe('1,200 of 1,500 AI runs');
		expect(planSummary({ id: 'free', label: 'Free', documents: 3, profiles: 1, ai_runs: 5 })).toBe(
			'3 CVs, 1 profile and 5 AI runs a month'
		);
		expect(
			planSummary({ id: 'pro', label: 'Pro', documents: 100, profiles: 10, ai_runs: 150 })
		).toBe('100 CVs, 10 profiles and 150 AI runs a month');
		// Periods are UTC, so the day does not move with the viewer's time zone.
		expect(formatDay('2026-11-01T00:00:00Z')).toBe('1 November');
	});

	it('finds the first limit that is reached', () => {
		const current = usage();
		expect(limitReached(current.ai_runs, current.documents)).toBeNull();
		expect(limitReached(current.ai_runs, current.profiles)).toBe(
			'You have 1 profile, the most on Free.'
		);
		expect(limitReached(undefined)).toBeNull();
	});

	it('says what an action makes when that limit blocks it', () => {
		const current = usage();
		const importing = { meter: current.profiles, what: 'Importing a CV makes a new profile.' };

		expect(blockedReason(current.ai_runs, importing)).toBe(
			'Importing a CV makes a new profile. You have 1 profile, the most on Free.'
		);
		const spent = { used: 5, limit: 5, message: 'You have used all 5 AI runs this month.' };
		expect(blockedReason(spent, importing)).toBe('You have used all 5 AI runs this month.');
		expect(blockedReason(current.ai_runs, { meter: current.documents, what: 'x' })).toBeNull();
	});

	it('offers an upgrade to Free users without a subscription to fix', () => {
		expect(canUpgrade(usage(), true)).toBe(true);
		expect(canUpgrade(usage(), false)).toBe(false);
		expect(canUpgrade(null, true)).toBe(false);
		expect(canUpgrade(subscribed('active'), true)).toBe(false);
		expect(canUpgrade(subscribed('cancelled', 'free'), true)).toBe(true);
		// A failed renewal is fixed by updating the card, not by subscribing again.
		expect(canUpgrade(subscribed('attention', 'free'), true)).toBe(false);
	});

	it('describes the subscription', () => {
		expect(subscriptionStatus(usage())).toBeNull();
		expect(subscriptionStatus(subscribed('active'))).toBe('Renews on 10 November.');
		expect(subscriptionStatus(subscribed('active', 'pro', null))).toBe(
			'Your subscription is active.'
		);
		expect(subscriptionStatus(subscribed('non_renewing'))).toBe(
			'Pro until 10 November. Your subscription will not renew.'
		);
		expect(subscriptionStatus(subscribed('attention'))).toBe(
			'The last payment did not go through. Update your card to keep Pro after 10 November.'
		);
		expect(subscriptionStatus(subscribed('attention', 'free'))).toBe(
			'The last payment did not go through, so you are on Free. Update your card to get Pro back.'
		);
		expect(subscriptionStatus(subscribed('cancelled', 'free'))).toBe(
			'Your Pro subscription has ended.'
		);
	});

	it('reads the reference Paystack adds to the callback URL', () => {
		const back = new URL('http://app.test/app/settings?tab=billing&trxref=ref_1&reference=ref_1');
		expect(paystackReference(back.searchParams)).toBe('ref_1');
		expect(paystackReference(new URLSearchParams('trxref=ref_2'))).toBe('ref_2');
		expect(paystackReference(new URLSearchParams('tab=billing'))).toBeNull();
	});
});
