import { StringStream } from '@codemirror/language';
import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import CodeEditor from '#lib/components/editor/CodeEditor.svelte';
import { typstParser } from '#lib/components/editor/typst-language.ts';

/** The tokens of source text, line by line, as [text, token] pairs without the blanks. */
function tokens(source: string): [string, string][] {
	const state = typstParser.startState!(2);
	const found: [string, string][] = [];
	for (const line of source.split('\n')) {
		const stream = new StringStream(line, 2, 2);
		while (!stream.eol()) {
			const token = typstParser.token(stream, state);
			const text = stream.current();
			stream.start = stream.pos;
			if (token) found.push([text, token]);
		}
	}
	return found;
}

describe('the Typst tokenizer', () => {
	it('reads keywords, calls, strings and numbers', () => {
		expect(tokens('#let navy = rgb("one")')).toEqual([
			['#let', 'keyword'],
			['rgb', 'variableName'],
			['"one"', 'string']
		]);
		expect(tokens('#set text(size: 10.5pt, lang: "en")')).toEqual([
			['#set', 'keyword'],
			['text', 'variableName'],
			['10.5pt', 'number'],
			['"en"', 'string']
		]);
		expect(tokens('#if x == none { split-row(a, b) }')).toEqual([
			['#if', 'keyword'],
			['none', 'atom'],
			['split-row', 'variableName']
		]);
	});

	it('reads comments, including a block comment over several lines', () => {
		expect(tokens('// a // b "not a string"')).toEqual([['// a // b "not a string"', 'comment']]);
		expect(tokens('a /* one\ntwo */ b')).toEqual([
			['/* one', 'comment'],
			['two */', 'comment']
		]);
	});

	it('keeps an escaped quote inside the string, and does not fail on odd input', () => {
		expect(tokens('"say \\"hi\\""')).toEqual([['"say \\"hi\\""', 'string']]);
		expect(() => tokens('"unterminated\n}{][ `~')).not.toThrow();
	});
});

describe('a read-only CodeEditor on Typst', () => {
	it('shows the source as text at once, then in a read-only editor', async () => {
		const { container } = render(CodeEditor, {
			value: '#import "/_lib/cv.typ": *\n// Slate',
			language: 'typst',
			label: 'Source of Slate',
			readonly: true
		});

		expect(screen.getByRole('region', { name: 'Source of Slate' })).toHaveTextContent(
			'#import "/_lib/cv.typ": *'
		);
		await waitFor(() => expect(container.querySelector('.cm-content')).not.toBeNull());
		const editor = screen.getByRole('textbox', { name: 'Source of Slate' });
		expect(editor).toHaveAttribute('aria-readonly', 'true');
		expect(editor).toHaveTextContent('// Slate');
		expect(screen.queryByRole('region', { name: 'Source of Slate' })).toBeNull();
	});
});
