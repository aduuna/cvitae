import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Kbd from '#lib/components/ui/Kbd.svelte';
import { text } from '../snippet';

describe('Kbd', () => {
	it('renders a mono keyboard key', () => {
		const { container } = render(Kbd, { children: text('Alt') });
		const kbd = container.querySelector('kbd');
		expect(kbd).toHaveTextContent('Alt');
		expect(kbd).toHaveClass('font-mono', 'text-xs', 'border-line', 'rounded-sm');
	});
});
