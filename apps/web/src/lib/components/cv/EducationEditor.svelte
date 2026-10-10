<script lang="ts">
	import Input from '#lib/components/ui/Input.svelte';
	import type { EducationItem } from '#lib/cv/types.ts';
	import DateRangeInput from './DateRangeInput.svelte';
	import ItemPanel from './ItemPanel.svelte';

	interface Props {
		item: EducationItem;
		ondelete: () => void;
	}

	let { item = $bindable(), ondelete }: Props = $props();

	const title = $derived([item.degree, item.institution].filter((part) => part.trim()).join(', '));
</script>

<ItemPanel {title} placeholder="New education" deleteLabel="Delete education" {ondelete}>
	<div class="grid grid-cols-1 gap-3 @md:grid-cols-2">
		<Input label="Institution" bind:value={item.institution} />
		<Input label="Degree" bind:value={item.degree} />
		<Input label="Location" bind:value={item.location} />
	</div>
	<DateRangeInput
		start={item.dates.start}
		end={item.dates.end}
		onchange={(start, end) => (item.dates = { start, end })}
	/>
</ItemPanel>
