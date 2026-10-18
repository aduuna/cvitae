<script lang="ts">
	import {
		buttonBase,
		buttonSizes,
		buttonVariants,
		type ButtonSize,
		type ButtonVariant
	} from '#lib/components/ui/Button.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import type { IconName } from '#lib/components/ui/icons.ts';

	interface Props {
		label: string;
		variant?: ButtonVariant;
		size?: ButtonSize;
		icon?: IconName;
	}

	let { label, variant = 'secondary', size = 'md', icon }: Props = $props();
</script>

<!-- A Button as it looks in the app, for pictures: the same classes, not a control. -->
<span class={[buttonBase, buttonVariants[variant], buttonSizes[size]]}>
	{#if icon}<Icon name={icon} />{/if}
	{label}
</span>
