import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Icon from '#lib/components/ui/Icon.svelte';
import { icons } from '#lib/components/ui/icons.ts';

function svg(container: HTMLElement): SVGSVGElement {
	const element = container.querySelector('svg');
	if (!element) throw new Error('no svg rendered');
	return element;
}

describe('Icon', () => {
	it('renders the named icon at 16px with a 1.5 stroke, hidden from assistive tech', () => {
		const { container } = render(Icon, { name: 'delete' });
		const element = svg(container);
		expect(element).toHaveAttribute('data-icon', 'delete');
		expect(element).toHaveAttribute('width', '16');
		expect(element).toHaveAttribute('height', '16');
		expect(element).toHaveAttribute('stroke-width', '1.5');
		expect(element).toHaveAttribute('stroke', 'currentColor');
		expect(element).toHaveAttribute('aria-hidden', 'true');
	});

	it('renders 20px for empty states', () => {
		const { container } = render(Icon, { name: 'documents', size: 20 });
		expect(svg(container)).toHaveAttribute('width', '20');
	});

	it('spins for the loading state', () => {
		const { container } = render(Icon, { name: 'loading', spin: true });
		expect(svg(container)).toHaveClass('animate-spin');
	});

	it('covers every purpose in the design table', () => {
		for (const name of [
			'documents',
			'profiles',
			'import',
			'tailor',
			'templates',
			'settings',
			'new',
			'duplicate',
			'delete',
			'download',
			'versions',
			'drag',
			'nav-collapse',
			'nav-expand',
			'placeholder-warning',
			'code',
			'form'
		]) {
			expect(icons).toHaveProperty(name);
		}
	});
});
