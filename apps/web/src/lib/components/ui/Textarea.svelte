<script lang="ts">
	import type { HTMLTextareaAttributes } from 'svelte/elements';
	import Field, { controlClass } from './Field.svelte';

	interface Props extends Omit<HTMLTextareaAttributes, 'class' | 'value'> {
		value?: string;
		label?: string;
		help?: string;
		error?: string;
		ref?: HTMLTextAreaElement;
	}

	let {
		value = $bindable(''),
		label,
		help,
		error,
		id: idProp,
		rows = 4,
		ref = $bindable(),
		...rest
	}: Props = $props();

	const fallbackId = $props.id();
	const id = $derived(idProp ?? fallbackId);
</script>

<Field {id} {label} {help} {error}>
	{#snippet children(control)}
		<textarea
			bind:this={ref}
			bind:value
			{id}
			{rows}
			{...rest}
			aria-invalid={control.invalid || undefined}
			aria-describedby={control.describedby}
			class="resize-y py-1.5 {controlClass(control.invalid)}"></textarea>
	{/snippet}
</Field>
