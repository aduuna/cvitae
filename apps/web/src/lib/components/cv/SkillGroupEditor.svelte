<script lang="ts">
	import Input from '#lib/components/ui/Input.svelte';
	import type { SkillGroup } from '#lib/cv/types.ts';
	import ItemPanel from './ItemPanel.svelte';
	import ListInput from './ListInput.svelte';

	interface Props {
		item: SkillGroup;
		ondelete: () => void;
	}

	let { item = $bindable(), ondelete }: Props = $props();
</script>

<ItemPanel
	id={item.id}
	title={item.label}
	placeholder="New skill group"
	deleteLabel="Delete skill group"
	{ondelete}
>
	<div class="grid grid-cols-1 gap-3 @md:grid-cols-[1fr_2fr]">
		<Input label="Label" bind:value={item.label} placeholder="Languages" />
		<ListInput label="Skills" bind:items={item.items} placeholder="Python, SQL, Go" />
	</div>
</ItemPanel>
