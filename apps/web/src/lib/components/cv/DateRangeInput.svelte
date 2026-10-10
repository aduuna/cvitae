<script lang="ts">
	import Input from '#lib/components/ui/Input.svelte';

	interface Props {
		start: string;
		/** Null means present. */
		end: string | null;
		onchange: (start: string, end: string | null) => void;
	}

	let { start, end, onchange }: Props = $props();
</script>

<div class="grid grid-cols-2 gap-3">
	<Input
		label="Start"
		placeholder="2021-03"
		value={start}
		oninput={(event) => onchange(event.currentTarget.value, end)}
	/>
	<Input
		label="End"
		placeholder="Present"
		help="Empty means present"
		value={end ?? ''}
		oninput={(event) =>
			onchange(start, event.currentTarget.value.trim() ? event.currentTarget.value : null)}
	/>
</div>
