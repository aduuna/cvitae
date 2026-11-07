import { EditorView } from '@codemirror/view';
import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import CodeEditor from '#lib/components/editor/CodeEditor.svelte';

/** The editor's view once its chunk has loaded. */
async function view(label: string): Promise<EditorView> {
	const content = await screen.findByRole('textbox', { name: label });
	const found = EditorView.findFromDOM(content.closest('.cm-editor') as HTMLElement);
	if (!found) throw new Error('no editor view');
	return found;
}

describe('CodeEditor', () => {
	it('shows the text at once, then in a labelled editor that reports edits', async () => {
		const onchange = vi.fn();
		render(CodeEditor, {
			value: '# Ama\n',
			language: 'markdown',
			label: 'CV as Markdown',
			onchange
		});

		expect(screen.getByRole('region', { name: 'CV as Markdown' })).toHaveTextContent('# Ama');
		const editor = await view('CV as Markdown');
		expect(editor.state.doc.toString()).toBe('# Ama\n');
		expect(screen.queryByRole('region', { name: 'CV as Markdown' })).toBeNull();
		editor.dispatch({ changes: { from: editor.state.doc.length, insert: 'Headline: Engineer' } });

		expect(onchange).toHaveBeenCalledWith('# Ama\nHeadline: Engineer');
	});

	it('replaces the text when the value changes from outside', async () => {
		const { rerender } = render(CodeEditor, {
			value: '// classic',
			language: 'typst',
			label: 'main.typ'
		});
		const editor = await view('main.typ');

		await rerender({ value: '// compact' });

		expect(editor.state.doc.toString()).toBe('// compact');
	});

	it('marks diagnostics at their line and column', async () => {
		render(CodeEditor, {
			value: 'Hello\n#unknown-thing\n',
			language: 'typst',
			label: 'main.typ',
			diagnostics: [{ line: 2, column: 2, message: 'unknown variable: unknown' }]
		});

		await waitFor(() =>
			expect(document.querySelector('.cm-lintRange-error')?.textContent).toBe('unknown')
		);
	});

	it('marks the whole line when there is no column, and clamps lines past the end', async () => {
		render(CodeEditor, {
			value: 'one\ntwo',
			language: 'markdown',
			label: 'CV as Markdown',
			diagnostics: [{ line: 9, message: 'Start bullets with "- "' }]
		});

		await waitFor(() =>
			expect(document.querySelector('.cm-lintRange-error')?.textContent).toBe('two')
		);
	});

	it('follows diagnostics that change, and clears them', async () => {
		const { rerender } = render(CodeEditor, {
			value: 'one\ntwo',
			language: 'typst',
			label: 'main.typ',
			diagnostics: [{ line: 1, message: 'first' }]
		});
		await waitFor(() =>
			expect(document.querySelector('.cm-lintRange-error')?.textContent).toBe('one')
		);

		await rerender({ diagnostics: [{ line: 2, message: 'second' }] });
		await waitFor(() =>
			expect(document.querySelector('.cm-lintRange-error')?.textContent).toBe('two')
		);

		await rerender({ diagnostics: [] });
		await waitFor(() => expect(document.querySelector('.cm-lintRange-error')).toBeNull());
	});

	it('highlights placeholders in Markdown as the form does', async () => {
		render(CodeEditor, {
			value: '- Served [[number of analysts]] analysts',
			language: 'markdown',
			label: 'CV as Markdown'
		});

		await waitFor(() =>
			expect(document.querySelector('.cm-cv-placeholder')?.textContent).toBe(
				'[[number of analysts]]'
			)
		);
	});

	it('can be read-only', async () => {
		render(CodeEditor, { value: '{}', language: 'json', label: 'data.json', readonly: true });

		const editor = await view('data.json');

		expect(editor.state.readOnly).toBe(true);
		expect(screen.getByRole('textbox', { name: 'data.json' })).toHaveAttribute(
			'aria-readonly',
			'true'
		);
	});

	it('does not trap the Tab key', async () => {
		render(CodeEditor, { value: 'a', language: 'typst', label: 'main.typ' });
		const editor = await view('main.typ');

		const handled = editor.contentDOM.dispatchEvent(
			new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })
		);

		// Not prevented: the browser moves focus on, and the text is unchanged.
		expect(handled).toBe(true);
		expect(editor.state.doc.toString()).toBe('a');
	});
});
