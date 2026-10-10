import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from '#lib/components/shell/Page.svelte';
import { text } from '../snippet';

describe('Page', () => {
	it('renders a 48px top bar with the one page title and sets the document title', () => {
		render(Page, { title: 'Templates' });
		const heading = screen.getByRole('heading', { level: 1, name: 'Templates' });
		expect(heading).toHaveClass('text-xl', 'font-semibold');
		expect(heading.parentElement).toHaveClass('h-12', 'border-b', 'border-line', 'bg-surface');
		expect(document.title).toBe('Templates - Vitae');
	});

	it('puts content in a centred 960px column with a skip-link target', () => {
		render(Page, { title: 'Profiles', children: text('Content') });
		const main = screen.getByRole('main');
		expect(main).toHaveAttribute('id', 'main');
		expect(screen.getByText('Content').parentElement).toHaveClass('max-w-240', 'mx-auto');
	});

	it('renders actions on the right of the top bar', () => {
		render(Page, { title: 'Documents', actions: text('New CV') });
		const header = screen.getByRole('banner');
		expect(header).toHaveTextContent('New CV');
	});

	it('uses the full width for the editor', () => {
		render(Page, { title: 'Backend CV', width: 'full', children: text('Editor') });
		expect(screen.getByText('Editor').parentElement).toBe(screen.getByRole('main'));
	});
});
