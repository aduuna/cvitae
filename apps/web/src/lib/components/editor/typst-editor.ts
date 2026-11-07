import { EditorState } from '@codemirror/state';
import { EditorView, lineNumbers } from '@codemirror/view';
import { typst, typstHighlight } from './typst-language.ts';

export interface EditorOptions {
	doc: string;
	/** Accessible name of the text area. */
	label: string;
	readonly: boolean;
	onchange?: (doc: string) => void;
}

const theme = EditorView.theme({
	'&': {
		backgroundColor: 'var(--color-surface)',
		color: 'var(--color-fg)',
		fontSize: 'var(--text-sm)',
		maxHeight: '60vh',
		border: '1px solid var(--color-line)',
		borderRadius: 'var(--radius-md)'
	},
	'&.cm-focused': {
		outline: '2px solid var(--color-accent)',
		outlineOffset: '2px'
	},
	'.cm-scroller': { fontFamily: 'var(--font-mono)', lineHeight: '1.6', overflow: 'auto' },
	'.cm-content': { caretColor: 'var(--color-accent)' },
	'.cm-gutters': {
		backgroundColor: 'var(--color-subtle)',
		color: 'var(--color-fg-faint)',
		border: 'none',
		borderRight: '1px solid var(--color-line)'
	},
	'&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection': {
		backgroundColor: 'color-mix(in srgb, var(--color-accent) 20%, transparent)'
	}
});

/** A CodeMirror 6 view of Typst source, on the app's tokens. Loaded lazily by TypstEditor. */
export function createEditor(parent: HTMLElement, options: EditorOptions): EditorView {
	return new EditorView({
		parent,
		state: EditorState.create({
			doc: options.doc,
			extensions: [
				lineNumbers(),
				typst,
				typstHighlight,
				theme,
				EditorState.readOnly.of(options.readonly),
				EditorView.contentAttributes.of({
					'aria-label': options.label,
					...(options.readonly ? { 'aria-readonly': 'true' } : {})
				}),
				EditorView.updateListener.of((update) => {
					if (update.docChanged) options.onchange?.(update.state.doc.toString());
				})
			]
		})
	});
}
