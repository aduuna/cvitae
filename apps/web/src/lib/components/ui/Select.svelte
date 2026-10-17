<script lang="ts" module>
	export interface SelectOption {
		value: string;
		label: string;
		disabled?: boolean;
	}
</script>

<script lang="ts">
	import type { HTMLSelectAttributes } from 'svelte/elements';
	import Field, { controlClass } from './Field.svelte';
	import Icon from './Icon.svelte';

	interface Props extends Omit<HTMLSelectAttributes, 'class' | 'value' | 'children' | 'multiple'> {
		options: SelectOption[];
		value?: string;
		label?: string;
		help?: string;
		error?: string;
		ref?: HTMLSelectElement;
	}

	let {
		options,
		value = $bindable(''),
		label,
		help,
		error,
		id: idProp,
		ref = $bindable(),
		...rest
	}: Props = $props();

	const fallbackId = $props.id();
	const id = $derived(idProp ?? fallbackId);
</script>

<Field {id} {label} {help} {error}>
	{#snippet children(control)}
		<div class="relative">
			<select
				bind:this={ref}
				bind:value
				{id}
				{...rest}
				aria-invalid={control.invalid || undefined}
				aria-describedby={[control.describedby, rest['aria-describedby']]
					.filter(Boolean)
					.join(' ') || undefined}
				class="h-8 appearance-none pr-8 {controlClass(control.invalid)}"
			>
				{#each options as option (option.value)}
					<option value={option.value} disabled={option.disabled}>{option.label}</option>
				{/each}
			</select>
			<span class="pointer-events-none absolute inset-y-0 right-2 flex items-center text-fg-muted">
				<Icon name="chevron-down" />
			</span>
		</div>
	{/snippet}
</Field>
