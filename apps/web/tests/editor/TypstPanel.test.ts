import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TypstPanel from '#lib/components/editor/TypstPanel.svelte';
import { templates } from '#lib/templates.svelte.ts';
import { fakeApi, json } from '../extension/fake-api.ts';

const DATA = '/api/v1/documents/doc-1/data.json';

function props(savedAt: string) {
	return {
		documentId: 'doc-1',
		templateId: 'classic',
		layout: null,
		diagnostics: [],
		savedAt,
		onreset: () => {}
	};
}

describe('the data.json tab', () => {
	beforeEach(() => templates.reset());
	afterEach(() => vi.unstubAllGlobals());

	it('shows the error of a failed refetch instead of the data it had before', async () => {
		let answers = 0;
		fakeApi({
			'GET /api/v1/templates/classic/source': () => json({ id: 'classic', source: '// classic' }),
			[`GET ${DATA}`]: () =>
				++answers === 1
					? json({ basics: { name: 'Ama' } })
					: json({ error: { code: 'unavailable', message: 'The renderer is busy.' } }, 503)
		});
		const { rerender } = render(TypstPanel, props('1'));

		await userEvent.click(screen.getByRole('tab', { name: 'data.json' }));
		const editor = await screen.findByRole('textbox', { name: 'data.json, read-only' });
		expect(editor).toHaveTextContent('"name": "Ama"');

		await rerender(props('2'));

		expect(await screen.findByRole('alert')).toHaveTextContent('The renderer is busy.');
		await waitFor(() =>
			expect(screen.queryByRole('textbox', { name: 'data.json, read-only' })).toBeNull()
		);
	});

	it('keeps showing the data while a refetch is on its way', async () => {
		fakeApi({
			'GET /api/v1/templates/classic/source': () => json({ id: 'classic', source: '// classic' }),
			[`GET ${DATA}`]: () => json({ basics: { name: 'Ama' } })
		});
		const { rerender } = render(TypstPanel, props('1'));
		await userEvent.click(screen.getByRole('tab', { name: 'data.json' }));
		await screen.findByRole('textbox', { name: 'data.json, read-only' });

		await rerender(props('2'));

		expect(screen.getByRole('textbox', { name: 'data.json, read-only' })).toBeInTheDocument();
		expect(screen.queryByRole('alert')).toBeNull();
	});
});
