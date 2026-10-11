<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Button from '#lib/components/ui/Button.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';

	interface Props {
		/** The api's message for the limit that is reached. */
		message: string;
		/** For `aria-describedby` on the control it disables. */
		id?: string;
		/** Offer the way to Pro. */
		upgrade?: boolean;
	}

	let { message, id, upgrade = false }: Props = $props();
</script>

<div
	{id}
	role="status"
	class="flex items-center gap-3 rounded-lg border border-line bg-surface p-4"
>
	<span class="text-fg"><Icon name="limit" /></span>
	<p class="min-w-0 flex-1 text-base text-fg">{message}</p>
	{#if upgrade}
		<Button size="sm" onclick={() => goto(resolve('/app/settings?tab=billing'))}>See plans</Button>
	{/if}
</div>
