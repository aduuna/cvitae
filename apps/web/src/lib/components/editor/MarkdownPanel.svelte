<script lang="ts">
	import { untrack } from 'svelte';
	import { fromMarkdown, toMarkdown, type MarkdownError } from '#lib/cv/markdown.ts';
	import type { CvContent } from '#lib/cv/types.ts';
	import CodeEditor from './CodeEditor.svelte';

	interface Props {
		content: CvContent;
		/** After each edit: whether the text has errors, so the content holds its last valid version. */
		onvalidity?: (valid: boolean) => void;
	}

	let { content = $bindable(), onvalidity }: Props = $props();

	const SHOWN_ERRORS = 5;

	// Written once: later edits come from this text, and outside changes remount the panel.
	let text = $state(toMarkdown(untrack(() => content)));
	let errors = $state<MarkdownError[]>([]);

	function onchange(next: string) {
		const result = fromMarkdown(next, content);
		if (result.ok) {
			errors = [];
			content = result.content;
		} else {
			errors = result.errors;
		}
		onvalidity?.(result.ok);
	}
</script>

<div class="flex h-full min-h-0 flex-col gap-3 p-4">
	<p class="text-sm text-fg-muted">
		Each <code class="font-mono">##</code> section ends with its kind, like
		<code class="font-mono">{'{experience}'}</code>. Fields such as
		<code class="font-mono">Role: ...</code> go right under an entry's
		<code class="font-mono">###</code> heading, before its bullets.
	</p>
	<div class="min-h-0 flex-1">
		<CodeEditor
			bind:value={text}
			language="markdown"
			label="CV as Markdown"
			fill
			diagnostics={errors}
			{onchange}
		/>
	</div>
	<div aria-live="polite" class="text-sm text-danger">
		{#if errors.length}
			<p class="font-medium">Not saved: fix these lines first.</p>
			<ul class="mt-1">
				{#each errors.slice(0, SHOWN_ERRORS) as error, index (index)}
					<li>Line {error.line}: {error.message}</li>
				{/each}
			</ul>
			{#if errors.length > SHOWN_ERRORS}
				<p class="mt-1">And {errors.length - SHOWN_ERRORS} more.</p>
			{/if}
		{/if}
	</div>
</div>
