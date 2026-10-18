<script lang="ts" module>
	// not-disabled rather than enabled: the same for buttons, and it also matches LinkButton's <a>.
	export const buttonVariants = {
		primary:
			'bg-accent text-accent-fg not-disabled:hover:bg-accent/85 not-disabled:active:bg-accent/75',
		secondary:
			'border border-line-strong bg-surface text-fg not-disabled:hover:border-fg-muted not-disabled:active:bg-muted',
		ghost: 'text-fg not-disabled:hover:bg-subtle not-disabled:active:bg-muted',
		danger:
			'border border-line-strong bg-surface text-danger not-disabled:hover:border-danger not-disabled:active:bg-muted'
	} as const;

	export const buttonSizes = {
		sm: 'h-7 gap-1.5 px-2.5',
		md: 'h-8 gap-2 px-3',
		lg: 'h-10 gap-2 px-4'
	} as const;

	/** Shared by Button, LinkButton and the landing page's pictures of the app. */
	export const buttonBase =
		'inline-flex shrink-0 items-center justify-center rounded-md text-base font-medium whitespace-nowrap transition-colors duration-120 ease-out select-none';

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
		buttonBase,
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
