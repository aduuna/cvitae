import {
	HighlightStyle,
	StreamLanguage,
	syntaxHighlighting,
	type StreamParser
} from '@codemirror/language';
import { tags } from '@lezer/highlight';

const KEYWORDS = new Set([
	'let',
	'set',
	'show',
	'import',
	'include',
	'if',
	'else',
	'for',
	'while',
	'in',
	'as',
	'return',
	'break',
	'continue',
	'context',
	'not',
	'and',
	'or'
]);
const ATOMS = new Set(['none', 'auto', 'true', 'false']);

interface State {
	/** Inside a block comment that continues from an earlier line. */
	comment: boolean;
}

/**
 * A small Typst tokenizer: comments, strings, keywords, function calls and numbers. It reads one
 * line at a time and never fails, so any source shows something sensible. It is for reading code,
 * not for checking it: the renderer is the judge of whether a template is valid.
 */
export const typstParser: StreamParser<State> = {
	name: 'typst',
	startState: () => ({ comment: false }),
	token(stream, state) {
		if (state.comment) {
			while (!stream.eol()) {
				if (stream.match('*/')) {
					state.comment = false;
					break;
				}
				stream.next();
			}
			return 'comment';
		}
		if (stream.eatSpace()) return null;
		if (stream.match('//')) {
			stream.skipToEnd();
			return 'comment';
		}
		if (stream.match('/*')) {
			state.comment = true;
			while (!stream.eol()) {
				if (stream.match('*/')) {
					state.comment = false;
					break;
				}
				stream.next();
			}
			return 'comment';
		}
		if (stream.match('"')) {
			let escaped = false;
			while (!stream.eol()) {
				const char = stream.next();
				if (escaped) escaped = false;
				else if (char === '\\') escaped = true;
				else if (char === '"') break;
			}
			return 'string';
		}
		if (stream.match(/^#?[A-Za-z_][\w-]*/)) {
			const word = stream.current().replace(/^#/, '');
			if (KEYWORDS.has(word)) return 'keyword';
			if (ATOMS.has(word)) return 'atom';
			return stream.peek() === '(' ? 'variableName' : null;
		}
		if (stream.match(/^\d+(?:\.\d+)?(?:pt|cm|mm|em|in|%|deg|fr)?/)) return 'number';
		stream.next();
		return null;
	}
};

export const typst = StreamLanguage.define(typstParser);

/** Weight and the muted token only: the app has no colour in its chrome, and code is no exception. */
export const typstHighlight = syntaxHighlighting(
	HighlightStyle.define([
		{ tag: tags.comment, color: 'var(--color-fg-muted)' },
		{ tag: tags.keyword, fontWeight: '600' },
		{ tag: tags.variableName, fontWeight: '500' }
	])
);
