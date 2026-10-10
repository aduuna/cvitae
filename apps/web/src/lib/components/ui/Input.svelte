<script lang="ts">
	import type { HTMLInputAttributes } from 'svelte/elements';
	import Field, { controlClass } from './Field.svelte';

	interface Props extends Omit<HTMLInputAttributes, 'class' | 'size' | 'value'> {
		value?: string;
		label?: string;
		help?: string;
		error?: string;
		ref?: HTMLInputElement;
	}

	let {
		value = $bindable(''),
		label,
		help,
		error,
		id: idProp,
		type = 'text',
		ref = $bindable(),
		...rest
	}: Props = $props();

	const fallbackId = $props.id();
	const id = $derived(idProp ?? fallbackId);
</script>

<Field {id} {label} {help} {error}>
	{#snippet children(control)}
		<input
			bind:this={ref}
			bind:value
			{id}
			{type}
			{...rest}
			aria-invalid={control.invalid || undefined}
			aria-describedby={control.describedby}
			class="h-8 {controlClass(control.invalid)}"
		/>
	{/snippet}
</Field>
