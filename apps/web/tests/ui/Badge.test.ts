import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Badge, { badgeVariants } from '#lib/components/ui/Badge.svelte';
import { text } from '../snippet';

describe('Badge', () => {
	it('defaults to neutral at caption size', () => {
		render(Badge, { children: text('Pro') });
		const badge = screen.getByText('Pro').parentElement!;
		expect(badge).toHaveAttribute('data-variant', 'neutral');
		expect(badge).toHaveClass('text-xs', 'font-medium', 'rounded-sm', 'bg-muted');
	});

	it.each(Object.entries(badgeVariants))('applies the %s variant', (variant, classes) => {
		render(Badge, { variant: variant as keyof typeof badgeVariants, children: text('Ejected') });
		expect(screen.getByText('Ejected').parentElement).toHaveClass(...classes.split(' '));
	});
});
