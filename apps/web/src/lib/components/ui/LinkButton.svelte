<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAnchorAttributes } from 'svelte/elements';
	import {
		buttonBase,
		buttonSizes,
		buttonVariants,
		type ButtonSize,
		type ButtonVariant
	} from './Button.svelte';
	import Icon from './Icon.svelte';
	import type { IconName } from './icons';

	/** A link that looks like a Button, for actions that navigate. */
	interface Props extends Omit<HTMLAnchorAttributes, 'class' | 'children'> {
		/** A route from resolve(), or a fragment on this page. */
		href: string;
		variant?: ButtonVariant;
		size?: ButtonSize;
		/** Optional leading icon. */
		icon?: IconName;
		children: Snippet;
	}

	let { href, variant = 'secondary', size = 'md', icon, children, ...rest }: Props = $props();
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- callers pass resolved routes -->
<a
	{href}
	{...rest}
	data-variant={variant}
	data-size={size}
	class={[buttonBase, buttonVariants[variant], buttonSizes[size]]}
>
	{#if icon}
		<Icon name={icon} />
	{/if}
	{@render children()}
</a>
<!-- eslint-enable svelte/no-navigation-without-resolve -->
