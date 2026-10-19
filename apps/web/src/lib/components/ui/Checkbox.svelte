<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLInputAttributes } from 'svelte/elements';

	interface Props extends Omit<HTMLInputAttributes, 'class' | 'type' | 'checked' | 'children'> {
		checked?: boolean;
		/** The label beside the box; plain text or a snippet for richer content. */
		label?: string;
		help?: string;
		children?: Snippet;
	}

	let { checked = $bindable(false), label, help, id: idProp, children, ...rest }: Props = $props();

	const fallbackId = $props.id();
	const id = $derived(idProp ?? fallbackId);
</script>

<div class="flex items-start gap-2">
	<input
		{id}
		type="checkbox"
		bind:checked
		{...rest}
		aria-describedby={help ? `${id}-help` : undefined}
		class="mt-0.5 size-4 shrink-0 cursor-pointer rounded-sm border border-line-strong accent-accent disabled:cursor-not-allowed disabled:opacity-40"
	/>
	<div class="flex min-w-0 flex-col gap-0.5">
		<label for={id} class="cursor-pointer text-base text-fg">
			{#if children}{@render children()}{:else}{label}{/if}
		</label>
		{#if help}
			<p id="{id}-help" class="text-sm text-fg-muted">{help}</p>
		{/if}
	</div>
</div>
