<script lang="ts" module>
	export const buttonVariants = {
		primary: 'bg-accent text-accent-fg enabled:hover:bg-accent/85 enabled:active:bg-accent/75',
		secondary:
			'border border-line-strong bg-surface text-fg enabled:hover:border-fg-muted enabled:active:bg-muted',
		ghost: 'text-fg enabled:hover:bg-subtle enabled:active:bg-muted',
		danger:
			'border border-line-strong bg-surface text-danger enabled:hover:border-danger enabled:active:bg-muted'
	} as const;

	export const buttonSizes = {
		sm: 'h-7 gap-1.5 px-2.5',
		md: 'h-8 gap-2 px-3',
		lg: 'h-10 gap-2 px-4'
	} as const;

	export type ButtonVariant = keyof typeof buttonVariants;
	export type ButtonSize = keyof typeof buttonSizes;
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import Icon from './Icon.svelte';
	import type { IconName } from './icons';

	interface Props extends Omit<HTMLButtonAttributes, 'class' | 'children'> {
		variant?: ButtonVariant;
		size?: ButtonSize;
		/** Optional leading icon. */
		icon?: IconName;
		/** Replaces the leading icon with a spinner and blocks clicks; the label stays. */
		loading?: boolean;
		ref?: HTMLButtonElement;
		children: Snippet;
	}

	let {
		variant = 'secondary',
		size = 'md',
		icon,
		loading = false,
		disabled = false,
		type = 'button',
		ref = $bindable(),
		children,
		...rest
	}: Props = $props();
</script>

<button
	bind:this={ref}
	{type}
	{...rest}
	disabled={disabled || loading}
	aria-busy={loading || undefined}
	data-variant={variant}
	data-size={size}
	class={[
		'inline-flex shrink-0 items-center justify-center rounded-md text-base font-medium whitespace-nowrap transition-colors duration-120 ease-out select-none',
		buttonVariants[variant],
		buttonSizes[size],
		disabled && 'cursor-not-allowed opacity-40',
		loading && 'cursor-wait'
	]}
>
	{#if loading}
		<Icon name="loading" spin />
	{:else if icon}
		<Icon name={icon} />
	{/if}
	{@render children()}
</button>
