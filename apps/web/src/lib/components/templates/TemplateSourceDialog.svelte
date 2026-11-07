<script lang="ts">
	import { errorMessage } from '#lib/api/client.ts';
	import CodeEditor from '#lib/components/editor/CodeEditor.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Dialog from '#lib/components/ui/Dialog.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { templates } from '#lib/templates.svelte.ts';

	interface Props {
		open: boolean;
		/** The template to read; its source loads each time the dialog opens. */
		template: { id: string; name: string } | null;
	}

	let { open = $bindable(), template }: Props = $props();

	let source = $state<string | null>(null);
	let failure = $state<string | null>(null);

	$effect(() => {
		if (!open || !template) return;
		let current = true;
		source = null;
		failure = null;
		templates.source(template.id).then(
			(loaded) => {
				if (current) source = loaded;
			},
			(error: unknown) => {
				if (current) failure = errorMessage(error);
			}
		);
		return () => {
			current = false;
		};
	});
</script>

<Dialog bind:open title="Source of {template?.name ?? 'template'}" size="lg">
	<div class="flex flex-col gap-3">
		<p class="text-sm text-fg-muted">
			This is the Typst that draws your CV in this template. You can read and copy it here; it
			cannot be edited.
		</p>
		{#if failure}
			<p role="alert" class="text-sm text-danger">{failure}</p>
		{:else if source === null}
			<Skeleton variant="block" height="lg" />
		{:else if template}
			<CodeEditor value={source} language="typst" label="Source of {template.name}" readonly />
		{/if}
	</div>
	{#snippet footer()}
		<Button variant="primary" onclick={() => (open = false)}>Close</Button>
	{/snippet}
</Dialog>
