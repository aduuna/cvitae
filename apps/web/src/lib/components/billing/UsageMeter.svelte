<script lang="ts">
	interface Props {
		label: string;
		used: number;
		limit: number;
		/** Under the bar, for example when AI runs reset. */
		caption?: string;
	}

	let { label, used, limit, caption }: Props = $props();

	const percent = $derived(limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 100);
	const number = new Intl.NumberFormat('en-GB');
</script>

<div class="flex flex-col gap-1.5">
	<div class="flex items-baseline justify-between gap-4 text-sm">
		<span class="font-medium text-fg">{label}</span>
		<span class="text-fg-muted tabular-nums">{number.format(used)} of {number.format(limit)}</span>
	</div>
	<div
		class="h-1 overflow-hidden rounded-sm bg-muted"
		role="meter"
		aria-label={label}
		aria-valuemin={0}
		aria-valuemax={limit}
		aria-valuenow={Math.min(used, limit)}
		aria-valuetext="{number.format(used)} of {number.format(limit)}"
	>
		<div class="h-full rounded-sm bg-accent" style:width="{percent}%"></div>
	</div>
	{#if caption}
		<p class="text-sm text-fg-muted">{caption}</p>
	{/if}
</div>
