<script lang="ts">
	import type { EditorView } from '@codemirror/view';
	import { onMount, untrack } from 'svelte';
	import type { CodeLanguage, EditorDiagnostic } from './code-editor.ts';

	interface Props {
		value: string;
		language: CodeLanguage;
		/** Accessible name of the editor, for example "main.typ" or "Source of Slate". */
		label: string;
		/** Editable unless read only: a template's source can be read, not edited. */
		readonly?: boolean;
		diagnostics?: EditorDiagnostic[];
		/** Fill the parent's height and scroll inside, as in the editor panel; otherwise it grows
		 * with the text up to 60vh. */
		fill?: boolean;
		onchange?: (value: string) => void;
	}

	let {
		value = $bindable(),
		language,
		label,
		readonly = false,
		diagnostics = [],
		fill = false,
		onchange
	}: Props = $props();

	let host: HTMLDivElement | undefined = $state();
	let view = $state.raw<EditorView | null>(null);
	let mark = $state.raw<typeof import('./code-editor.ts').markDiagnostics | null>(null);

	// CodeMirror is a separate chunk, loaded when the first editor opens. Until then, and if it
	// cannot load, the text shows as plain text.
	onMount(() => {
		let gone = false;
		let created: EditorView | null = null;
		import('./code-editor.ts')
			.then((chunk) => {
				if (gone || !host) return;
				created = chunk.createEditor(host, {
					doc: untrack(() => value),
					language,
					label,
					readonly,
					fill,
					onchange: (next) => {
						value = next;
						onchange?.(next);
					}
				});
				mark = chunk.markDiagnostics;
				view = created;
			})
			.catch(() => {});
		return () => {
			gone = true;
			created?.destroy();
		};
	});

	// Changes from outside (a version restore, a reset) replace the text.
	$effect(() => {
		const next = value;
		if (view && view.state.doc.toString() !== next) {
			view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: next } });
		}
	});

	$effect(() => {
		if (view && mark) mark(view, diagnostics);
	});
</script>

<div
	bind:this={host}
	class={[fill && 'h-full min-h-0', !view && 'hidden']}
	data-testid="code-editor"
></div>
{#if !view}
	<!-- A scrolling region has to be reachable by keyboard to be read. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<pre
		role="region"
		tabindex="0"
		aria-label={label}
		class={[
			'overflow-auto rounded-md border border-line-strong bg-surface p-3 font-mono text-sm text-fg',
			fill ? 'h-full' : 'max-h-[60vh]'
		]}>{value}</pre>
{/if}
