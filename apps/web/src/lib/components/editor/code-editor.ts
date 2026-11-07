import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import { json } from '@codemirror/lang-json';
import {
	bracketMatching,
	HighlightStyle,
	indentOnInput,
	syntaxHighlighting
} from '@codemirror/language';
import { lintGutter, setDiagnostics, type Diagnostic } from '@codemirror/lint';
import { EditorState, type Extension, type Text } from '@codemirror/state';
import {
	Decoration,
	drawSelection,
	EditorView,
	keymap,
	lineNumbers,
	MatchDecorator,
	ViewPlugin,
	type DecorationSet,
	type ViewUpdate
} from '@codemirror/view';
import { tags } from '@lezer/highlight';
import { cvMarkdown } from './markdown-language.ts';
import { typst } from './typst-language.ts';

/** A problem to mark in the text. Lines and columns are 1-based, as Typst reports them. */
export interface EditorDiagnostic {
	line: number;
	column?: number | null;
	message: string;
}

export type CodeLanguage = 'markdown' | 'typst' | 'json';

export interface EditorOptions {
	doc: string;
	language: CodeLanguage;
	/** Accessible name of the text area. */
	label: string;
	readonly: boolean;
	/** Fill the parent's height, scrolling inside; otherwise grow with the text up to 60vh. */
	fill: boolean;
	onchange?: (doc: string) => void;
}

// Token styles stay in the grey scale of docs/DESIGN.md, so they follow the theme: weight for
// structure, the muted colour for comments, strings and marks.
const highlight = HighlightStyle.define([
	{ tag: [tags.keyword, tags.heading, tags.strong], fontWeight: '600' },
	{ tag: tags.variableName, fontWeight: '500' },
	{ tag: [tags.comment, tags.processingInstruction, tags.meta], color: 'var(--color-fg-muted)' },
	{ tag: [tags.string, tags.url, tags.link, tags.labelName], color: 'var(--color-fg-muted)' }
]);

// [[placeholders]] in CV text look as they do in the form (docs/DESIGN.md, Placeholder).
const placeholderMatcher = new MatchDecorator({
	regexp: /\[\[[^\n]+?\]\]/g,
	decoration: Decoration.mark({ class: 'cm-cv-placeholder' })
});
const placeholders = ViewPlugin.fromClass(
	class {
		decorations: DecorationSet;
		constructor(editor: EditorView) {
			this.decorations = placeholderMatcher.createDeco(editor);
		}
		update(update: ViewUpdate) {
			this.decorations = placeholderMatcher.updateDeco(update, this.decorations);
		}
	},
	{ decorations: (plugin) => plugin.decorations }
);

const theme = EditorView.theme({
	'&': {
		backgroundColor: 'var(--color-surface)',
		color: 'var(--color-fg)',
		fontSize: 'var(--text-sm)',
		border: '1px solid var(--color-line-strong)',
		borderRadius: 'var(--radius-md)'
	},
	'&.cm-focused': { outline: '2px solid var(--color-accent)', outlineOffset: '2px' },
	'.cm-scroller': { fontFamily: 'var(--font-mono)', lineHeight: '1.6', overflow: 'auto' },
	'.cm-content': { caretColor: 'var(--color-fg)', padding: '8px 0' },
	'.cm-content:focus-visible': { outline: 'none' },
	'.cm-gutters': {
		backgroundColor: 'var(--color-subtle)',
		color: 'var(--color-fg-muted)',
		border: 'none',
		borderRight: '1px solid var(--color-line)'
	},
	'.cm-cursor': { borderLeftColor: 'var(--color-fg)' },
	'&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection': {
		backgroundColor: 'var(--color-muted)'
	},
	'.cm-lintRange-error': {
		backgroundImage: 'none',
		textDecoration: 'underline wavy var(--color-danger)',
		textUnderlineOffset: '3px'
	},
	'.cm-tooltip': {
		backgroundColor: 'var(--color-surface)',
		color: 'var(--color-fg)',
		border: '1px solid var(--color-line)',
		borderRadius: 'var(--radius-md)'
	},
	'.cm-diagnostic-error': { borderLeftColor: 'var(--color-danger)' },
	'.cm-cv-placeholder, .cm-cv-placeholder *': {
		backgroundColor: 'var(--color-placeholder)',
		color: 'var(--color-placeholder-fg)',
		borderRadius: 'var(--radius-sm)'
	},
	'&.cm-focused .cm-matchingBracket': {
		backgroundColor: 'var(--color-muted)',
		outline: '1px solid var(--color-line-strong)'
	},
	'&.cm-focused .cm-nonmatchingBracket': {
		backgroundColor: 'transparent',
		outline: '1px solid var(--color-danger)'
	}
});

const sizing = (fill: boolean) =>
	EditorView.theme({ '&': fill ? { height: '100%' } : { maxHeight: '60vh' } });

function languageExtension(language: CodeLanguage): Extension {
	if (language === 'markdown') return [cvMarkdown, placeholders];
	if (language === 'json') return json();
	return typst;
}

/** Diagnostics as CodeMirror ranges: the column to the end of its word, or the whole line. */
function toRanges(doc: Text, items: EditorDiagnostic[]): Diagnostic[] {
	return items.map((item) => {
		const line = doc.line(Math.min(Math.max(1, item.line), doc.lines));
		if (!item.column) {
			return { from: line.from, to: line.to, severity: 'error', message: item.message };
		}
		const from = Math.min(line.from + item.column - 1, line.to);
		const rest = line.text.slice(from - line.from);
		const length = /^\w+/.exec(rest)?.[0].length ?? 1;
		return {
			from,
			to: Math.min(from + length, line.to),
			severity: 'error',
			message: item.message
		};
	});
}

/** Mark `items` in the text, replacing the marks of the last call. */
export function markDiagnostics(view: EditorView, items: EditorDiagnostic[]): void {
	view.dispatch(setDiagnostics(view.state, toRanges(view.state.doc, items)));
}

/** A CodeMirror 6 view on the app's tokens. Loaded lazily by CodeEditor. */
export function createEditor(parent: HTMLElement, options: EditorOptions): EditorView {
	return new EditorView({
		parent,
		state: EditorState.create({
			doc: options.doc,
			extensions: [
				lineNumbers(),
				history(),
				drawSelection(),
				indentOnInput(),
				bracketMatching(),
				lintGutter(),
				// No Tab binding: Tab leaves the editor, so the keyboard is never trapped in it.
				keymap.of([...defaultKeymap, ...historyKeymap]),
				languageExtension(options.language),
				syntaxHighlighting(highlight),
				theme,
				sizing(options.fill),
				EditorState.readOnly.of(options.readonly),
				EditorView.lineWrapping,
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
