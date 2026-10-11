import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Placeholder from '#lib/components/ui/Placeholder.svelte';
import { text } from '../snippet';

describe('Placeholder', () => {
	it('highlights a gap with the placeholder token', () => {
		render(Placeholder, { children: text('number of users') });

		const gap = screen.getByText('number of users').parentElement;
		expect(gap).toHaveClass('bg-placeholder', 'text-placeholder-fg', 'rounded-sm');
	});
});
