<script lang="ts" module>
	/** Line drawings in static/illustrations/, with their intrinsic sizes. */
	export const cartoons = {
		tailor: { width: 560, height: 420 },
		stack: { width: 290, height: 410 },
		'cover-letter': { width: 240, height: 150 },
		extension: { width: 240, height: 150 },
		ats: { width: 240, height: 150 }
	} as const;
</script>

<script lang="ts">
	import { asset } from '$app/paths';
	import { theme } from '#lib/theme.svelte.ts';

	interface Props {
		name: keyof typeof cartoons;
		/** What the drawing shows; empty when the text beside it says the same. */
		label?: string;
	}

	let { name, label = '' }: Props = $props();
</script>

<!-- Black line art like the logo; inverted it reads as white on the dark theme. -->
<img
	src={asset(`illustrations/${name}.svg`)}
	alt={label}
	width={cartoons[name].width}
	height={cartoons[name].height}
	draggable="false"
	class={['h-auto w-full select-none', theme.resolved === 'dark' && 'invert']}
/>
