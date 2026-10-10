<script lang="ts" module>
	export interface SegmentedOption<T extends string = string> {
		value: T;
		label: string;
	}
</script>

<script lang="ts" generics="T extends string">
	import { nextIndex } from './roving';

	interface Props {
		/** 2 to 4 options. */
		options: SegmentedOption<T>[];
		value: T;
		/** Accessible name of the group, for example "AI provider". */
		label: string;
		disabled?: boolean;
		onchange?: (value: T) => void;
	}

	let { options, value = $bindable(), label, disabled = false, onchange }: Props = $props();

	let buttons: HTMLButtonElement[] = $state([]);

	function select(index: number) {
		const option = options[index];
		if (!option || disabled) return;
		if (option.value !== value) {
			value = option.value;
			onchange?.(option.value);
		}
	}

	function onkeydown(event: KeyboardEvent, index: number) {
		const next = nextIndex(event.key, index, options.length);
		if (next === null) return;
		event.preventDefault();
		select(next);
		buttons[next]?.focus();
	}
</script>

<div
	role="radiogroup"
	aria-label={label}
	aria-disabled={disabled || undefined}
	class={[
		'inline-flex h-8 items-center gap-0.5 rounded-md bg-muted p-0.5',
		disabled && 'opacity-40'
	]}
>
	{#each options as option, index (option.value)}
		{@const checked = option.value === value}
		<button
			bind:this={buttons[index]}
			type="button"
			role="radio"
			aria-checked={checked}
			tabindex={checked ? 0 : -1}
			{disabled}
			onclick={() => select(index)}
			onkeydown={(event) => onkeydown(event, index)}
			class={[
				'h-7 rounded-sm px-3 text-base transition-colors duration-120 ease-out disabled:cursor-not-allowed',
				checked
					? 'bg-surface font-medium text-fg shadow-page'
					: 'text-fg-muted enabled:hover:text-fg'
			]}
		>
			{option.label}
		</button>
	{/each}
</div>
