import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { buttonSizes, buttonVariants } from '#lib/components/ui/Button.svelte';
import LinkButton from '#lib/components/ui/LinkButton.svelte';
import { text } from '../snippet';

describe('LinkButton', () => {
	it.each(Object.entries(buttonVariants))('looks like a %s button', (variant, classes) => {
		render(LinkButton, {
			href: '/login',
			variant: variant as keyof typeof buttonVariants,
			children: text('Sign in')
		});
		const link = screen.getByRole('link', { name: 'Sign in' });
		expect(link).toHaveAttribute('data-variant', variant);
		expect(link).toHaveClass(...classes.split(' '));
	});

	it.each(Object.entries(buttonSizes))('applies the %s size classes', (size, classes) => {
		render(LinkButton, {
			href: '/login',
			size: size as keyof typeof buttonSizes,
			children: text('Sign in')
		});
		expect(screen.getByRole('link')).toHaveClass(...classes.split(' '));
	});

	it('navigates to its href, secondary and medium by default', () => {
		render(LinkButton, { href: '/login', children: text('Sign in') });
		const link = screen.getByRole('link', { name: 'Sign in' });
		expect(link).toHaveAttribute('href', '/login');
		expect(link).toHaveAttribute('data-variant', 'secondary');
		expect(link).toHaveAttribute('data-size', 'md');
	});

	it('renders a leading icon and passes other attributes through', () => {
		render(LinkButton, {
			href: '#how',
			icon: 'download',
			'aria-describedby': 'hint',
			children: text('Export PDF')
		});
		const link = screen.getByRole('link', { name: 'Export PDF' });
		expect(link.querySelector('[data-icon="download"]')).not.toBeNull();
		expect(link).toHaveAttribute('aria-describedby', 'hint');
	});
});
