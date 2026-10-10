<script lang="ts" module>
	export const iconButtonVariants = {
		ghost: 'text-fg enabled:hover:bg-subtle enabled:active:bg-muted',
		secondary:
			'border border-line-strong bg-surface text-fg enabled:hover:border-fg-muted enabled:active:bg-muted'
	} as const;

	export const iconButtonSizes = {
		sm: 'size-7',
		md: 'size-8'
	} as const;
</script>

<script lang="ts">
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import Icon from './Icon.svelte';
	import type { IconName } from './icons';
	import Tooltip from './Tooltip.svelte';

	interface Props extends Omit<HTMLButtonAttributes, 'class' | 'children' | 'aria-label'> {
		/** Accessible name and tooltip text. Required: the button has no visible label. */
		label: string;
		icon: IconName;
		variant?: keyof typeof iconButtonVariants;
		size?: keyof typeof iconButtonSizes;
		tooltipSide?: 'top' | 'right' | 'bottom';
		ref?: HTMLButtonElement;
	}

	let {
		label,
		icon,
		variant = 'ghost',
		size = 'md',
		tooltipSide = 'top',
		disabled = false,
		type = 'button',
		ref = $bindable(),
		...rest
	}: Props = $props();
</script>

<Tooltip text={label} side={tooltipSide} describe={false}>
	{#snippet children(trigger)}
		<button
			bind:this={ref}
			{type}
			{disabled}
			aria-label={label}
			{...rest}
			{...trigger}
			data-variant={variant}
			class={[
				'inline-flex shrink-0 items-center justify-center rounded-md transition-colors duration-120 ease-out',
				iconButtonVariants[variant],
				iconButtonSizes[size],
				disabled && 'cursor-not-allowed opacity-40'
			]}
		>
			<Icon name={icon} />
		</button>
	{/snippet}
</Tooltip>
