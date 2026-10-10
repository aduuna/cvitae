import { createRawSnippet, type Snippet } from 'svelte';

/** A children snippet rendering plain text, for passing to components in tests. */
export function text(content: string): Snippet {
	return createRawSnippet(() => ({ render: () => `<span>${content}</span>` }));
}
