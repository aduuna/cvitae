<script lang="ts">
	import Input from '#lib/components/ui/Input.svelte';
	import type { Engagement } from '#lib/cv/types.ts';
	import BulletList from './BulletList.svelte';
	import DateRangeInput from './DateRangeInput.svelte';
	import ItemPanel from './ItemPanel.svelte';

	interface Props {
		engagement: Engagement;
		ondelete: () => void;
	}

	let { engagement = $bindable(), ondelete }: Props = $props();

	const title = $derived(
		[engagement.label, engagement.name].filter((part) => part.trim()).join(': ')
	);
</script>

<ItemPanel {title} placeholder="New client" deleteLabel="Delete client" {ondelete}>
	<div class="grid grid-cols-1 gap-3 @md:grid-cols-2">
		<Input label="Label" bind:value={engagement.label} help="Client, Contingent worker, ..." />
		<Input label="Name" bind:value={engagement.name} />
		<Input label="Location" bind:value={engagement.location} />
	</div>
	<DateRangeInput
		start={engagement.dates?.start ?? ''}
		end={engagement.dates?.end ?? null}
		onchange={(start, end) => (engagement.dates = start.trim() || end ? { start, end } : null)}
	/>
	<BulletList
		bind:bullets={engagement.bullets}
		label="Bullets for {engagement.name || 'this client'}"
	/>
</ItemPanel>
