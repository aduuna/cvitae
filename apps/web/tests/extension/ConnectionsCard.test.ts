import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ConnectionsCard from '#lib/components/extension/ConnectionsCard.svelte';
import { fakeApi } from './fake-api.ts';

const connection = {
	id: 'c1',
	label: 'Chrome on macOS',
	created_at: '2026-10-01T09:00:00Z',
	last_used_at: null
};

describe('ConnectionsCard', () => {
	afterEach(() => vi.unstubAllGlobals());

	it('waits for the list, then says when no browser is connected', () => {
		const { rerender } = render(ConnectionsCard, { connections: null });
		expect(screen.queryByText('No browser is connected.')).toBeNull();

		rerender({ connections: [] });
		expect(screen.getByText('No browser is connected.')).toBeVisible();
	});

	it('lists connected browsers and disconnects one', async () => {
		const api = fakeApi({
			'DELETE /api/v1/extension/connections/c1': () => new Response(null, { status: 204 })
		});
		render(ConnectionsCard, {
			connections: [
				connection,
				{ ...connection, id: 'c2', label: 'Firefox on Linux', last_used_at: '2026-10-02T09:00:00Z' }
			]
		});

		const chrome = screen.getByText('Chrome on macOS').closest('li')!;
		expect(within(chrome).getByText(/not used yet/)).toBeVisible();
		expect(screen.getByText(/last used/)).toBeVisible();

		await userEvent.click(within(chrome).getByRole('button', { name: 'Disconnect' }));

		expect(api.calls).toContain('DELETE /api/v1/extension/connections/c1');
		expect(screen.queryByText('Chrome on macOS')).toBeNull();
		expect(screen.getByText('Firefox on Linux')).toBeVisible();
	});
});
