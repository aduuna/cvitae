import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import EmptyState from '#lib/components/ui/EmptyState.svelte';

describe('EmptyState', () => {
	it('shows a 20px icon, a title, a hint and one primary action', async () => {
		const onaction = vi.fn();
		const { container } = render(EmptyState, {
			icon: 'documents',
			title: 'No CVs yet',
			hint: 'Create one from a profile or tailor one to a job.',
			actionLabel: 'New CV',
			actionIcon: 'new',
			onaction
		});
		expect(container.querySelector('[data-icon="documents"]')).toHaveAttribute('width', '20');
		expect(screen.getByText('No CVs yet')).toBeInTheDocument();
		expect(screen.getByText(/Create one/)).toHaveClass('text-sm', 'text-fg-muted');
		const action = screen.getByRole('button', { name: 'New CV' });
		expect(action).toHaveAttribute('data-variant', 'primary');
		await userEvent.click(action);
		expect(onaction).toHaveBeenCalledOnce();
	});

	it('omits the action when none is given', () => {
		render(EmptyState, { icon: 'templates', title: 'Nothing here', hint: 'Check back later.' });
		expect(screen.queryByRole('button')).toBeNull();
	});
});
