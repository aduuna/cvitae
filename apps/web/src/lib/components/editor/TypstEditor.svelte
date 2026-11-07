<script lang="ts">
	import type { EditorView } from '@codemirror/view';
	import { onMount } from 'svelte';

	interface Props {
		/** The Typst source. */
		value: string;
		/** Accessible name of the text area, for example "Source of Slate". */
		label: string;
		/** Read only by default: custom templates can be read, not edited. */
		readonly?: boolean;
		onchange?: (value: string) => void;
	}

	let { value, label, readonly = true, onchange }: Props = $props();

	let host: HTMLDivElement | undefined = $state();
	let view = $state.raw<EditorView | null>(null);

	// CodeMirror is a separate chunk, loaded when the first editor opens. Until then, and if it
	// cannot load, the source shows as plain text.
	onMount(() => {
		let gone = false;
		let created: EditorView | null = null;
		import('./typst-editor.ts')
			.then(({ createEditor }) => {
				if (gone || !host) return;
				created = createEditor(host, { doc: value, label, readonly, onchange });
				view = created;
			})
			.catch(() => {});
		return () => {
			gone = true;
			created?.destroy();
		};
	});

	$effect(() => {
		if (view && view.state.doc.toString() !== value) {
			view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } });
		}
	});
</script>

<div bind:this={host} class={view ? '' : 'hidden'} data-testid="typst-editor"></div>
{#if !view}
	<!-- A scrolling region has to be reachable by keyboard to be read. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<pre
		role="region"
		tabindex="0"
		aria-label={label}
		class="max-h-[60vh] overflow-auto rounded-md border border-line bg-surface p-3 font-mono text-sm text-fg">{value}</pre>
{/if}
