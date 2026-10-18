<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		/** What the picture shows, read out in place of its contents. */
		label: string;
		children: Snippet;
	}

	let { label, children }: Props = $props();
</script>

<!-- A picture of the app drawn with its own styles: one image to assistive tech, never operable. -->
<div
	role="img"
	aria-label={label}
	class="pointer-events-none min-w-0 rounded-lg border border-line bg-canvas p-4 text-left select-none sm:p-6"
>
	{@render children()}
</div>
