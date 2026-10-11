<script lang="ts" module>
	export const logoSizes = {
		sm: 'size-6',
		lg: 'size-12'
	} as const;
</script>

<script lang="ts">
	import { asset } from '$app/paths';
	import { theme } from '#lib/theme.svelte.ts';

	interface Props {
		size?: keyof typeof logoSizes;
		/** Alt text when the logo stands alone; leave empty when the name is next to it. */
		label?: string;
	}

	let { size = 'sm', label = '' }: Props = $props();
</script>

<!-- The logo is black line art; inverted it reads as white on the dark theme. -->
<img
	src={asset('logo.svg')}
	alt={label}
	class={['shrink-0', logoSizes[size], theme.resolved === 'dark' && 'invert']}
/>
