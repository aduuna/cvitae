<script lang="ts">
	import CvEditor from '#lib/components/cv/CvEditor.svelte';
	import type { CvContent } from '#lib/cv/types.ts';

	let { initial, disabled = false }: { initial: CvContent; disabled?: boolean } = $props();

	// Deeply reactive, like the content the app edits.
	// svelte-ignore state_referenced_locally
	let content = $state(initial);

	export function current(): CvContent {
		return $state.snapshot(content);
	}
</script>

<CvEditor bind:content {disabled} />
