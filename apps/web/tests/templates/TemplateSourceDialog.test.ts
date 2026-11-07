import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TemplateSourceDialog from '#lib/components/templates/TemplateSourceDialog.svelte';
import { templates } from '#lib/templates.svelte.ts';
import { fakeApi, json } from '../extension/fake-api.ts';

const SLATE = { id: 'u-aaaaaaaaa2', name: 'Slate' };
const SOURCE = 'GET /api/v1/templates/u-aaaaaaaaa2/source';

describe('the view source dialog', () => {
	// The catalog keeps sources for the session, so each test starts without them.
	beforeEach(() => templates.reset());
	afterEach(() => vi.unstubAllGlobals());

	it('loads the source of the template and shows it read only', async () => {
		const { calls } = fakeApi({
			[SOURCE]: () => json({ id: SLATE.id, source: '#import "/_lib/cv.typ": *\n// Slate' })
		});

		render(TemplateSourceDialog, { open: true, template: SLATE });

		const dialog = screen.getByRole('dialog', { name: 'Source of Slate' });
		expect(dialog).toHaveTextContent('it cannot be edited');
		await waitFor(() => expect(dialog).toHaveTextContent('// Slate'));
		expect(calls).toEqual([SOURCE]);
	});

	it('says when the source could not load', async () => {
		fakeApi({
			[SOURCE]: () =>
				json({ error: { code: 'not_found', message: 'This template does not exist.' } }, 404)
		});

		render(TemplateSourceDialog, { open: true, template: SLATE });

		expect(await screen.findByRole('alert')).toHaveTextContent('This template does not exist.');
	});

	it('does not ask for anything while closed, and closes from the footer', async () => {
		const { calls } = fakeApi({
			[SOURCE]: () => json({ id: SLATE.id, source: 'x' })
		});

		render(TemplateSourceDialog, { open: false, template: SLATE });
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(calls).toEqual([]);

		const { unmount } = render(TemplateSourceDialog, { open: true, template: SLATE });
		const dialog = screen.getByRole('dialog', { name: 'Source of Slate' });
		await waitFor(() => expect(dialog).toHaveTextContent('x'));
		await userEvent.click(
			screen.getAllByRole('button', { name: 'Close' }).find((b) => dialog.contains(b))!
		);
		expect(screen.queryByRole('dialog')).toBeNull();
		unmount();
	});
});
