<script lang="ts">
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import Tabs from '#lib/components/ui/Tabs.svelte';
	import type { Diagnostic } from '#lib/cv/types.ts';
	import { templates } from '#lib/templates.svelte.ts';
	import CodeEditor from './CodeEditor.svelte';
	import type { EditorDiagnostic } from './code-editor.ts';

	interface Props {
		documentId: string;
		templateId: string;
		/** The CV's own main.typ; null while it follows the template. */
		layout: string | null;
		/** Diagnostics from the last preview. */
		diagnostics: Diagnostic[];
		/** When the CV was last saved, so data.json follows the content. */
		savedAt: string;
		/** "Reset to template" was chosen; the caller confirms and clears the layout. */
		onreset: () => void;
	}

	let {
		documentId,
		templateId,
		layout = $bindable(),
		diagnostics,
		savedAt,
		onreset
	}: Props = $props();

	let tab = $state('main');
	let source = $state<string | null>(null);
	let sourceError = $state<string | null>(null);
	let data = $state<string | null>(null);
	let dataError = $state<string | null>(null);

	const text = $derived(layout ?? source);
	const layoutDiagnostics = $derived<EditorDiagnostic[]>(
		diagnostics.flatMap((item) =>
			item.line && (!item.file || /(^|\/)main\.typ$/.test(item.file))
				? [{ line: item.line, column: item.column, message: item.message }]
				: []
		)
	);

	$effect(() => {
		const id = templateId;
		source = null;
		sourceError = null;
		templates.source(id).then(
			(value) => {
				if (id === templateId) source = value;
			},
			(error: unknown) => {
				if (id === templateId) sourceError = errorMessage(error);
			}
		);
	});

	$effect(() => {
		if (tab !== 'data') return;
		void savedAt;
		const controller = new AbortController();
		dataError = null;
		unwrap(
			api.GET('/api/v1/documents/{document_id}/data.json', {
				params: { path: { document_id: documentId } },
				signal: controller.signal
			})
		).then(
			(value) => (data = JSON.stringify(value, null, 2)),
			(error: unknown) => {
				if (!controller.signal.aborted) dataError = errorMessage(error);
			}
		);
		return () => controller.abort();
	});

	function onchange(next: string) {
		// Back to exactly the template's code: the CV follows the template again.
		layout = next === source ? null : next;
	}
</script>

<div class="flex h-full min-h-0 flex-col gap-3 p-4">
	<div class="flex items-start justify-between gap-3">
		<p class="text-sm text-fg-muted">
			{layout === null
				? `This is the ${templates.name(templateId)} layout. Your first edit gives this CV its own.`
				: 'This CV has its own layout.'}
			The content comes from data.json; edit it in Form or Markdown.
		</p>
		{#if layout !== null}
			<Button size="sm" variant="ghost" onclick={onreset}>Reset to template</Button>
		{/if}
	</div>
	<div class="min-h-0 flex-1">
		<Tabs
			fill
			label="Layout files"
			tabs={[
				{ id: 'main', label: 'main.typ' },
				{ id: 'data', label: 'data.json' }
			]}
			bind:value={tab}
		>
			{#snippet panel(id)}
				{#if id === 'main'}
					{#if text !== null}
						<CodeEditor
							value={text}
							language="typst"
							label="main.typ"
							diagnostics={layoutDiagnostics}
							{onchange}
						/>
					{:else if sourceError}
						<p role="alert" class="text-sm text-danger">{sourceError}</p>
					{:else}
						<Skeleton lines={8} />
					{/if}
				{:else if data !== null}
					<CodeEditor value={data} language="json" label="data.json, read-only" readonly />
				{:else if dataError}
					<p role="alert" class="text-sm text-danger">{dataError}</p>
				{:else}
					<Skeleton lines={8} />
				{/if}
			{/snippet}
		</Tabs>
	</div>
</div>
