<script lang="ts">
	import { modelOptions } from '#lib/ai/models.ts';
	import Select from '#lib/components/ui/Select.svelte';
	import type { AiModel, AiModelInfo } from '#lib/cv/types.ts';

	interface Props {
		value: AiModel | null;
		/** The models the server offers. */
		models: AiModelInfo[];
		plan?: 'free' | 'pro';
		/** With plans enforced, Pro models are disabled for Free users. */
		enforced?: boolean;
		label?: string;
		help?: string;
		disabled?: boolean;
	}

	let {
		value = $bindable(),
		models,
		plan = 'free',
		enforced = false,
		label = 'AI model',
		help,
		disabled = false
	}: Props = $props();

	const options = $derived(modelOptions(models, { plan, enforced }));
	let selected = $derived(value ?? '');
</script>

{#if models.length === 0}
	<div class="flex flex-col gap-1.5">
		<span class="text-sm font-medium text-fg">{label}</span>
		<p class="text-sm text-fg-muted">AI is not set up on this server yet.</p>
	</div>
{:else}
	<Select
		{label}
		{help}
		{options}
		{disabled}
		bind:value={() => selected, (next) => (value = (selected = next) as AiModel)}
	/>
{/if}
