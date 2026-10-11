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

/** "3 of 5 AI runs" for the side nav. */
export function runsLabel(meter: Meter): string {
	return `${number.format(meter.used)} of ${number.format(meter.limit)} AI runs`;
}

/** "3 CVs, 1 profile and 5 AI runs a month". */
export function planSummary(plan: PlanInfo): string {
	return `${count(plan.documents, 'CV', 'CVs')}, ${count(plan.profiles, 'profile', 'profiles')} and ${count(plan.ai_runs, 'AI run', 'AI runs')} a month`;
}

/** Why an action is blocked: the first limit that is reached, or null. */
export function limitReached(...meters: (Meter | undefined)[]): string | null {
	return meters.find((meter) => meter?.message)?.message ?? null;
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
