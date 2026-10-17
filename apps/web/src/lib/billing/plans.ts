import type { Schemas } from '#lib/api/client.ts';

export type Usage = Schemas['Usage'];
export type Meter = Schemas['Meter'];
export type PlanInfo = Schemas['PlanInfo'];

const number = new Intl.NumberFormat('en-GB');

function count(n: number, one: string, many: string): string {
	return `${number.format(n)} ${n === 1 ? one : many}`;
}

/** "10 November", in UTC like the api's periods. */
export function formatDay(iso: string): string {
	return new Intl.DateTimeFormat('en-GB', {
		day: 'numeric',
		month: 'long',
		timeZone: 'UTC'
	}).format(new Date(iso));
}

/**
 * "4 CVs and 2 profiles", or against a smaller plan "100 CVs, 10 profiles and 7 times the AI usage".
 * AI runs are shown as AI usage, never as counts (docs/PRODUCT.md, Plans and limits).
 */
export function planSummary(plan: PlanInfo, smaller?: PlanInfo): string {
	const documents = count(plan.documents, 'CV', 'CVs');
	const profiles = count(plan.profiles, 'profile', 'profiles');
	if (!smaller) return `${documents} and ${profiles}`;
	const times = Math.floor(plan.ai_runs / smaller.ai_runs);
	return `${documents}, ${profiles} and ${times} times the AI usage`;
}

/** Why an action is blocked: the first limit that is reached, or null. */
export function limitReached(...meters: (Meter | undefined)[]): string | null {
	return meters.find((meter) => meter?.message)?.message ?? null;
}

/**
 * Why an action that takes AI usage and makes something (a profile, a CV) is blocked, or null. The
 * limit on what it makes says what the action makes, so the reason reads on its own.
 */
export function blockedReason(
	runs: Meter | undefined,
	makes: { meter: Meter | undefined; what: string }
): string | null {
	if (runs?.message) return runs.message;
	if (makes.meter?.message) return `${makes.what} ${makes.meter.message}`;
	return null;
}

/** A Free user on a server where Paystack is set up, with no subscription to fix instead (a
 * failed renewal is fixed by updating the card, not by subscribing again). */
export function canUpgrade(usage: Usage | null, billingEnabled: boolean): boolean {
	const subscription = usage?.subscription;
	return (
		billingEnabled &&
		usage?.plan === 'free' &&
		(!subscription || subscription.status === 'cancelled')
	);
}

/** One line about the Paystack subscription for Settings, or null when there is none. */
export function subscriptionStatus(usage: Usage): string | null {
	const subscription = usage.subscription;
	if (!subscription) return null;
	const until = subscription.current_period_end ? formatDay(subscription.current_period_end) : null;
	switch (subscription.status) {
		case 'active':
			return until ? `Renews on ${until}.` : 'Your subscription is active.';
		case 'non_renewing':
			return until
				? `Pro until ${until}. Your subscription will not renew.`
				: 'Pro until the end of the period. Your subscription will not renew.';
		case 'attention':
			return usage.plan === 'pro'
				? `The last payment did not go through. Update your card to keep Pro${until ? ` after ${until}` : ''}.`
				: 'The last payment did not go through, so you are on Free. Update your card to get Pro back.';
		case 'cancelled':
			return 'Your Pro subscription has ended.';
	}
}

/** The reference Paystack adds to the callback URL's query after checkout. */
export function paystackReference(query: Pick<URLSearchParams, 'get'>): string | null {
	return query.get('reference') ?? query.get('trxref');
}
