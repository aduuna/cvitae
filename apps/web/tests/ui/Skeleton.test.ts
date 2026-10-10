import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Skeleton, { skeletonHeights } from '#lib/components/ui/Skeleton.svelte';

describe('Skeleton', () => {
	it('announces loading and renders pulsing lines with a shorter last line', () => {
		const { container } = render(Skeleton, { lines: 4 });
		expect(screen.getByRole('status')).toHaveTextContent('Loading');
		const lines = container.querySelectorAll('[data-skeleton="line"]');
		expect(lines).toHaveLength(4);
		expect(lines[0]).toHaveClass('w-full', 'bg-muted', 'animate-pulse');
		expect(lines[3]).toHaveClass('w-2/3');
	});

	it.each(Object.entries(skeletonHeights))('renders a %s block', (height, cls) => {
		const { container } = render(Skeleton, {
			variant: 'block',
			height: height as keyof typeof skeletonHeights
		});
		expect(container.querySelector('[data-skeleton="block"]')).toHaveClass(cls, 'bg-muted');
	});
});
