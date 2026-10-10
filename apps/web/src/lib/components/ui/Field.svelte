<script lang="ts" module>
	/** Shared look of Input, Textarea and Select (docs/DESIGN.md, Components). */
	export function controlClass(invalid: boolean): string {
		return [
			'w-full rounded-md border bg-surface px-2.5 text-base text-fg transition-colors duration-120 ease-out',
			'placeholder:text-fg-faint disabled:cursor-not-allowed disabled:opacity-40',
			invalid ? 'border-danger' : 'border-line-strong'
		].join(' ');
	}

	export interface FieldControl {
		describedby: string | undefined;
		invalid: boolean;
	}
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		id: string;
		label?: string;
		help?: string;
		error?: string;
		children: Snippet<[FieldControl]>;
	}

	let { id, label, help, error, children }: Props = $props();

	const messageId = $derived(error ? `${id}-error` : help ? `${id}-help` : undefined);
</script>

<div class="flex flex-col gap-1.5">
	{#if label}
		<label for={id} class="text-sm font-medium text-fg">{label}</label>
	{/if}
	{@render children({ describedby: messageId, invalid: !!error })}
	{#if error}
		<p id={messageId} class="text-sm text-danger">{error}</p>
	{:else if help}
		<p id={messageId} class="text-sm text-fg-muted">{help}</p>
	{/if}
</div>
