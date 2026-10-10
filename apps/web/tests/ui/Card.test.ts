import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Card, { cardPadding } from '#lib/components/ui/Card.svelte';
import { text } from '../snippet';

describe('Card', () => {
	it('is a bordered surface with optional heading', () => {
		const { container } = render(Card, { title: 'Account', children: text('Body') });
		const card = container.querySelector('section')!;
		expect(card).toHaveClass('rounded-lg', 'border', 'border-line', 'bg-surface', cardPadding.md);
		expect(screen.getByRole('heading', { name: 'Account' })).toHaveClass('text-lg');
		expect(screen.getByText('Body')).toBeInTheDocument();
	});

	it('can drop padding for full-width rows', () => {
		const { container } = render(Card, { padding: 'none', children: text('Rows') });
		expect(container.querySelector('section')).not.toHaveClass(cardPadding.md);
		expect(screen.queryByRole('heading')).toBeNull();
	});
});
