<script lang="ts" module>
	export const toastVariants = {
		info: 'border-line',
		error: 'border-danger'
	} as const;
</script>

<script lang="ts">
	import Icon from './Icon.svelte';
	import IconButton from './IconButton.svelte';
	import { toast } from './toasts.svelte';
</script>

<section
	aria-label="Notifications"
	aria-live="polite"
	class="pointer-events-none fixed right-4 bottom-4 z-50 flex w-80 flex-col gap-2"
>
	{#each toast.items as item (item.id)}
		<div
			role={item.kind === 'error' ? 'alert' : 'status'}
			data-kind={item.kind}
			class={[
				'pointer-events-auto flex animate-pop-in items-start gap-2 rounded-lg border bg-surface py-2 pr-2 pl-3 text-base text-fg shadow-pop',
				toastVariants[item.kind]
			]}
		>
			{#if item.kind === 'error'}
				<span class="mt-0.5 text-danger"><Icon name="placeholder-warning" /></span>
			{/if}
			<p class="mt-0.5 flex-1">{item.message}</p>
			<IconButton label="Dismiss" icon="close" size="sm" onclick={() => toast.dismiss(item.id)} />
		</div>
	{/each}
</section>
