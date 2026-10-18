<script lang="ts">
	interface Props {
		options: string[];
		selected: string;
	}

	let { options, selected }: Props = $props();
</script>

<!-- A SegmentedControl as it looks in the app, for pictures: the same classes, not a control. -->
<span class="inline-flex h-8 items-center gap-0.5 rounded-md bg-muted p-0.5">
	{#each options as option (option)}
		<span
			class={[
				'inline-flex h-7 items-center rounded-sm px-3 text-base',
				option === selected ? 'bg-surface font-medium text-fg shadow-page' : 'text-fg-muted'
			]}
		>
			{option}
		</span>
	{/each}
</span>
