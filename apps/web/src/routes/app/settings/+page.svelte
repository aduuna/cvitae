<script lang="ts">
	import { onMount } from 'svelte';
	import { errorMessage } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import Page from '#lib/components/shell/Page.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import { modelLabel, pickModel } from '#lib/ai/models.ts';
	import ModelSelect from '#lib/components/ai/ModelSelect.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import type { AiModel } from '#lib/cv/types.ts';

	let name = $state('');
	let loaded = $state(false);
	let saving = $state(false);
	let signingOut = $state(false);
	let model = $state<AiModel | null>(null);
	let savedModel: AiModel | null = null;

	const unchanged = $derived((session.me?.display_name ?? '') === name.trim());

	onMount(async () => {
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
					Used first on Import and Tailor; you can switch for any run. Claude and Gemini work under
					the same rule: they may select, reorder and reword what you wrote, and never add facts.
				</p>
			</div>
		{:else}
			<Skeleton lines={2} />
		{/if}
	</Card>
</Page>
