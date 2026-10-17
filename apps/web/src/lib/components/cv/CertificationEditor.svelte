<script lang="ts">
	import Input from '#lib/components/ui/Input.svelte';
	import type { CertificationItem } from '#lib/cv/types.ts';
	import ItemPanel from './ItemPanel.svelte';

	interface Props {
		item: CertificationItem;
		ondelete: () => void;
	}

	let { item = $bindable(), ondelete }: Props = $props();
</script>

<ItemPanel
	id={item.id}
	title={item.name}
	placeholder="New certification"
	deleteLabel="Delete certification"
	{ondelete}
>
	<div class="grid grid-cols-1 gap-3 @md:grid-cols-3">
		<Input label="Name" bind:value={item.name} />
		<Input label="Issuer" bind:value={item.issuer} />
		<Input label="Date" bind:value={item.date} placeholder="2023-04" />
	</div>
</ItemPanel>
