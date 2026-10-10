<script lang="ts">
	import Input from '#lib/components/ui/Input.svelte';
	import type { ProjectItem } from '#lib/cv/types.ts';
	import BulletList from './BulletList.svelte';
	import ItemPanel from './ItemPanel.svelte';

	interface Props {
		item: ProjectItem;
		ondelete: () => void;
	}

	let { item = $bindable(), ondelete }: Props = $props();
</script>

<ItemPanel title={item.name} placeholder="New project" deleteLabel="Delete project" {ondelete}>
	<div class="grid grid-cols-1 gap-3 @md:grid-cols-2">
		<Input label="Name" bind:value={item.name} />
		<Input
			label="Link"
			type="url"
			placeholder="https://"
			value={item.url ?? ''}
			oninput={(event) => (item.url = event.currentTarget.value.trim() || null)}
		/>
		<Input label="Status" bind:value={item.status} placeholder="Open source, in development" />
		<Input label="Year" bind:value={item.year} placeholder="2024" />
	</div>
	<BulletList bind:bullets={item.bullets} label="Bullets for {item.name || 'this project'}" />
</ItemPanel>
