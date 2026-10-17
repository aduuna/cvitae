<script lang="ts">
	interface Props {
		label: string;
		used: number;
		limit: number;
		/** Show the share used ("15%") instead of the counts ("3 of 20"), as for AI usage. */
		percent?: boolean;
		/** Under the bar, for example when AI usage resets. */
		caption?: string;
	}

	let { label, used, limit, percent = false, caption }: Props = $props();

	// Rounded down, so 100% always means the limit is reached.
	const share = $derived(limit > 0 ? Math.min(100, Math.floor((used / limit) * 100)) : 100);
	const number = new Intl.NumberFormat('en-GB');
	const value = $derived(
		percent ? `${share}%` : `${number.format(used)} of ${number.format(limit)}`
	);
</script>

<div class="flex flex-col gap-1.5">
	<div class="flex items-baseline justify-between gap-4 text-sm">
		<span class="font-medium text-fg">{label}</span>
		<span class="text-fg-muted tabular-nums">{value}</span>
	</div>
	<div
		class="h-1 overflow-hidden rounded-sm bg-muted"
		role="meter"
		aria-label={label}
		aria-valuemin={0}
		aria-valuemax={percent ? 100 : limit}
		aria-valuenow={percent ? share : Math.min(used, limit)}
		aria-valuetext={value}
	>
		<div class="h-full rounded-sm bg-accent" style:width="{share}%"></div>
	</div>
	{#if caption}
		<p class="text-sm text-fg-muted">{caption}</p>
	{/if}
</div>
