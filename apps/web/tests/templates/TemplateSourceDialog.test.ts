import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import TemplateSourceDialog from '#lib/components/templates/TemplateSourceDialog.svelte';
import { fakeApi, json } from '../extension/fake-api.ts';

const SLATE = { id: 'u-aaaaaaaaa2', name: 'Slate' };

describe('the view source dialog', () => {
	afterEach(() => vi.unstubAllGlobals());

	it('loads the source of the template and shows it read only', async () => {
		const { calls } = fakeApi({
			'GET /api/v1/templates/custom/u-aaaaaaaaa2/source': () =>
				json({ ...SLATE, main_typ: '#import "/_lib/cv.typ": *\n// Slate' })
		});

		render(TemplateSourceDialog, { open: true, template: SLATE });

		const dialog = screen.getByRole('dialog', { name: 'Source of Slate' });
		expect(dialog).toHaveTextContent('it cannot be edited');
		await waitFor(() => expect(dialog).toHaveTextContent('// Slate'));
		expect(calls).toEqual(['GET /api/v1/templates/custom/u-aaaaaaaaa2/source']);
	});

	it('says when the source could not load', async () => {
		fakeApi({
			'GET /api/v1/templates/custom/u-aaaaaaaaa2/source': () =>
				json({ error: { code: 'not_found', message: 'This template does not exist.' } }, 404)
		});

		render(TemplateSourceDialog, { open: true, template: SLATE });

		expect(await screen.findByRole('alert')).toHaveTextContent('This template does not exist.');
	});

	it('does not ask for anything while closed, and closes from the footer', async () => {
		const { calls } = fakeApi({
			'GET /api/v1/templates/custom/u-aaaaaaaaa2/source': () => json({ ...SLATE, main_typ: 'x' })
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
