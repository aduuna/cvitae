<script lang="ts">
	import Input from '#lib/components/ui/Input.svelte';
	import { splitList } from '#lib/cv/factory.ts';

	interface Props {
		items: string[];
		label: string;
		placeholder?: string;
	}

	let { items = $bindable(), label, placeholder }: Props = $props();

	// While focused, the field shows exactly what the user typed (a trailing comma, spaces). Otherwise
	// it shows the items, so changes from elsewhere, such as a version restore, appear.
	let draft = $state<string | null>(null);
	const text = $derived(draft ?? items.join(', '));
</script>

<Input
	{label}
	{placeholder}
	help="Separate with commas"
	value={text}
	onfocus={() => (draft = items.join(', '))}
	oninput={(event) => {
		draft = event.currentTarget.value;
		items = splitList(draft);
	}}
	onblur={() => (draft = null)}
/>
