<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import {
		canUpgrade,
		formatDay,
		paystackReference,
		planSummary,
		subscriptionStatus
	} from '#lib/billing/plans.ts';
	import UsageMeter from '#lib/components/billing/UsageMeter.svelte';
	import Page from '#lib/components/shell/Page.svelte';
	import Badge from '#lib/components/ui/Badge.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import { modelLabel, pickModel } from '#lib/ai/models.ts';
	import ModelSelect from '#lib/components/ai/ModelSelect.svelte';
	import SegmentedControl from '#lib/components/ui/SegmentedControl.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import type { AiModel } from '#lib/cv/types.ts';
	import { theme, themeOptions } from '#lib/theme.svelte.ts';

	let name = $state('');
	let loaded = $state(false);
	let saving = $state(false);
	let signingOut = $state(false);
	let model = $state<AiModel | null>(null);
	let savedModel: AiModel | null = null;
	let billing = $state<'upgrade' | 'manage' | 'verify' | null>(null);
	let billingCard = $state<HTMLElement>();

	const usage = $derived(session.usage);
	const pro = $derived(session.plans.find((plan) => plan.id === 'pro'));
	const current = $derived(session.plans.find((plan) => plan.id === usage?.plan));
	const subscription = $derived(usage?.subscription);

	const unchanged = $derived((session.me?.display_name ?? '') === name.trim());

	onMount(async () => {
		const reference = paystackReference(page.url.searchParams);
		if (reference) await verifyPayment(reference);
		try {
			await session.refreshUsage();
		} catch (error) {
			toast.error(errorMessage(error));
		}
		if (page.url.searchParams.get('tab') === 'billing') {
			await tick();
			billingCard?.scrollIntoView({ block: 'start' });
		}
		try {
			const me = await session.loadMe();
			name = me.display_name ?? '';
			model = savedModel = pickModel(
				me.preferred_ai_model,
				session.aiModels,
				session.defaultAiModel
			);
			loaded = true;
		} catch (error) {
			toast.error(errorMessage(error));
		}
	});

	async function saveName(event: SubmitEvent) {
		event.preventDefault();
		saving = true;
		try {
			await session.updateMe({ display_name: name.trim() });
			toast.info('Name saved.');
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			saving = false;
		}
	}

	async function saveModel(value: AiModel) {
		try {
			await session.updateMe({ preferred_ai_model: value });
			savedModel = value;
			toast.info(`New imports and tailoring use ${modelLabel(value, session.aiModels)}.`);
		} catch (error) {
			model = savedModel;
			toast.error(errorMessage(error));
		}
	}

	$effect(() => {
		if (loaded && model && model !== savedModel) void saveModel(model);
	});

	/** Back from Paystack's checkout: confirm the payment, then drop the reference from the URL. */
	async function verifyPayment(reference: string) {
		billing = 'verify';
		try {
			await unwrap(api.POST('/api/v1/billing/verify', { body: { reference } }));
			await session.refreshMe();
			toast.info('You are on Pro now.');
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			billing = null;
			await goto(resolve('/app/settings?tab=billing'), { replace: true, shallow: true });
		}
	}

	async function upgrade() {
		billing = 'upgrade';
		try {
			const checkout = await unwrap(api.POST('/api/v1/billing/checkout'));
			window.location.assign(checkout.authorization_url);
		} catch (error) {
			toast.error(errorMessage(error));
			billing = null;
		}
	}

	async function manage() {
		billing = 'manage';
		try {
			const link = await unwrap(api.GET('/api/v1/billing/manage-link'));
			window.location.assign(link.url);
		} catch (error) {
			toast.error(errorMessage(error));
			billing = null;
		}
	}

	async function signOut() {
		signingOut = true;
		try {
			await session.signOut();
		} catch (error) {
			toast.error(errorMessage(error));
			signingOut = false;
		}
	}
</script>

<Page title="Settings">
	<Card title="Account">
		{#if loaded}
			<div class="flex flex-col gap-4">
				<form class="flex items-end gap-2" onsubmit={saveName}>
					<div class="flex-1">
						<Input label="Name" autocomplete="name" maxlength={200} bind:value={name} />
					</div>
					<Button type="submit" loading={saving} disabled={unchanged}>Save name</Button>
				</form>
				<Input
					label="Email"
					value={session.me?.email ?? ''}
					readonly
					help="The address you sign in with."
				/>
				<div>
					<Button icon="sign-out" loading={signingOut} onclick={signOut}>Sign out</Button>
				</div>
			</div>
		{:else}
			<Skeleton lines={3} />
		{/if}
	</Card>

	<Card title="AI">
		{#if loaded}
			<div class="flex flex-col gap-3">
				<ModelSelect
					bind:value={model}
					models={session.aiModels}
					plan={session.me?.plan}
					enforced={session.plansEnforced}
					label="Default AI model"
				/>
				<p class="text-sm text-fg-muted">
					Used first on Import and Tailor; you can switch for any run. Every model works under the
					same rule: it may select, reorder and reword what you wrote, and never adds facts.
				</p>
			</div>
		{:else}
			<Skeleton lines={2} />
		{/if}
	</Card>

	<div id="billing" class="scroll-mt-6" bind:this={billingCard}>
		<Card title="Billing">
			{#if usage && billing !== 'verify'}
				{@const status = subscriptionStatus(usage)}
				<div class="flex flex-col gap-5">
					<div class="flex flex-col gap-1">
						<div class="flex items-center gap-2">
							<span class="text-base font-medium text-fg">Your plan</span>
							<Badge>{current?.label ?? usage.plan}</Badge>
						</div>
						{#if current}
							<p class="text-sm text-fg-muted">
								{planSummary(current)}{usage.plan === 'pro' ? ', and the Pro AI models' : ''}.
							</p>
						{/if}
						{#if status}
							<p class="text-sm text-fg">{status}</p>
						{/if}
					</div>

					<div class="flex flex-col gap-4">
						<UsageMeter
							label="AI usage this month"
							used={usage.ai_runs.used}
							limit={usage.ai_runs.limit}
							percent
							caption="Resets on {formatDay(usage.period_end)}."
						/>
						<UsageMeter label="CVs" used={usage.documents.used} limit={usage.documents.limit} />
						<UsageMeter label="Profiles" used={usage.profiles.used} limit={usage.profiles.limit} />
					</div>

					{#if canUpgrade(usage, session.billingEnabled)}
						<div class="flex flex-col items-start gap-2">
							<Button
								variant="primary"
								loading={billing === 'upgrade'}
								disabled={billing !== null}
								onclick={upgrade}
							>
								Upgrade to Pro
							</Button>
							{#if pro}
								<p class="text-sm text-fg-muted">
									Pro includes {planSummary(pro, current)}, and the Pro AI models. You pay monthly
									on Paystack and can cancel at any time.
								</p>
							{/if}
						</div>
					{:else if usage.plan === 'free' && !subscription}
						<p class="text-sm text-fg-muted">Upgrades are not available on this server yet.</p>
					{/if}

					{#if subscription && subscription.status !== 'cancelled'}
						{#if subscription.manageable}
							<div class="flex flex-col items-start gap-2">
								<Button loading={billing === 'manage'} disabled={billing !== null} onclick={manage}>
									Manage subscription
								</Button>
								<p class="text-sm text-fg-muted">Update your card or cancel on Paystack.</p>
							</div>
						{:else}
							<p class="text-sm text-fg-muted">
								Paystack is still setting up your subscription. Reload this page in a minute to
								manage it.
							</p>
						{/if}
					{/if}
				</div>
			{:else}
				<Skeleton lines={4} />
			{/if}
		</Card>
	</div>

	<Card title="Appearance">
		<div class="flex flex-col gap-3">
			<SegmentedControl label="Theme" options={themeOptions} bind:value={theme.preference} />
			<p class="text-sm text-fg-muted">
				System follows your device setting. The choice is saved in this browser. CV previews stay
				black on white, as they print.
			</p>
		</div>
	</Card>
</Page>
