<script lang="ts">
	import Button from './Button.svelte';
	import Icon from './Icon.svelte';
	import type { IconName } from './icons';

	interface Props {
		icon: IconName;
		/** One line. */
		title: string;
		/** One line. */
		hint: string;
		/** The one primary action, a verb such as "New CV". */
		actionLabel?: string;
		actionIcon?: IconName;
		onaction?: () => void;
	}

	let { icon, title, hint, actionLabel, actionIcon, onaction }: Props = $props();
</script>

<div class="flex flex-col items-center gap-1 px-6 py-12 text-center">
	<span class="mb-2 text-fg-muted"><Icon name={icon} size={20} /></span>
	<p class="text-base font-medium text-fg">{title}</p>
	<p class="text-sm text-fg-muted">{hint}</p>
	{#if actionLabel && onaction}
		<div class="mt-4">
			<Button variant="primary" icon={actionIcon} onclick={onaction}>{actionLabel}</Button>
		</div>
	{/if}
</div>
