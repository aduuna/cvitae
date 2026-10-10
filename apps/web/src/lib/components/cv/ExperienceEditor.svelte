<script lang="ts">
	import Button from '#lib/components/ui/Button.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import { newEngagement } from '#lib/cv/factory.ts';
	import type { ExperienceItem } from '#lib/cv/types.ts';
	import BulletList from './BulletList.svelte';
	import DateRangeInput from './DateRangeInput.svelte';
	import EngagementEditor from './EngagementEditor.svelte';
	import ItemPanel from './ItemPanel.svelte';
	import ListInput from './ListInput.svelte';
	import SortableList from './SortableList.svelte';

	interface Props {
		item: ExperienceItem;
		ondelete: () => void;
	}

	let { item = $bindable(), ondelete }: Props = $props();

	const title = $derived([item.role, item.org].filter((part) => part.trim()).join(', '));
</script>

<ItemPanel {title} placeholder="New role" deleteLabel="Delete role" {ondelete}>
	<div class="grid grid-cols-1 gap-3 @md:grid-cols-2">
		<Input label="Organisation" bind:value={item.org} />
		<Input label="Role" bind:value={item.role} />
		<Input label="Location" bind:value={item.location} />
	</div>
	<DateRangeInput
		start={item.dates.start}
		end={item.dates.end}
		onchange={(start, end) => (item.dates = { start, end })}
	/>
	<ListInput label="Tech stack" bind:items={item.stack} placeholder="Python, Spark, AWS" />
	<BulletList bind:bullets={item.bullets} label="Bullets for {item.org || 'this role'}" />

	{#if item.engagements.length > 0}
		<div class="flex flex-col gap-2">
			<p class="text-sm font-medium text-fg">Clients and placements</p>
			<SortableList bind:items={item.engagements} noun="client" label="Clients for {item.org}">
				{#snippet row(entry, index)}
					<EngagementEditor
						bind:engagement={() => entry, (value) => (item.engagements[index] = value)}
						ondelete={() => item.engagements.splice(index, 1)}
					/>
				{/snippet}
			</SortableList>
		</div>
	{/if}
	<div>
		<Button
			variant="ghost"
			size="sm"
			icon="new"
			onclick={() => item.engagements.push(newEngagement())}
		>
			Add client
		</Button>
	</div>
</ItemPanel>
