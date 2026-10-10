import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Button, { buttonSizes, buttonVariants } from '#lib/components/ui/Button.svelte';
import { text } from '../snippet';

describe('Button', () => {
	it.each(Object.entries(buttonVariants))('applies the %s variant classes', (variant, classes) => {
		render(Button, { variant: variant as keyof typeof buttonVariants, children: text('Save') });
		const button = screen.getByRole('button', { name: 'Save' });
		expect(button).toHaveAttribute('data-variant', variant);
		expect(button).toHaveClass(...classes.split(' '));
	});

	it.each(Object.entries(buttonSizes))('applies the %s size classes', (size, classes) => {
		render(Button, { size: size as keyof typeof buttonSizes, children: text('Save') });
		expect(screen.getByRole('button')).toHaveClass(...classes.split(' '));
	});

	it('defaults to a secondary, medium, type=button button', () => {
		render(Button, { children: text('Save') });
		const button = screen.getByRole('button');
		expect(button).toHaveAttribute('type', 'button');
		expect(button).toHaveAttribute('data-variant', 'secondary');
		expect(button).toHaveAttribute('data-size', 'md');
	});

	it('renders a leading icon', () => {
		render(Button, { icon: 'new', children: text('New CV') });
		const button = screen.getByRole('button', { name: 'New CV' });
		expect(button.querySelector('[data-icon="new"]')).not.toBeNull();
	});

	it('replaces the icon with a spinner while loading, keeping the label', async () => {
		const onclick = vi.fn();
		render(Button, { icon: 'download', loading: true, onclick, children: text('Export PDF') });
		const button = screen.getByRole('button', { name: 'Export PDF' });
		expect(button.querySelectorAll('svg')).toHaveLength(1);
		expect(button.querySelector('[data-icon="loading"]')).not.toBeNull();
		expect(button.querySelector('[data-icon="download"]')).toBeNull();
		expect(button).toHaveAttribute('aria-busy', 'true');
		await userEvent.click(button);
		expect(onclick).not.toHaveBeenCalled();
	});

	it('activates with the keyboard', async () => {
		const user = userEvent.setup();
		const onclick = vi.fn();
		render(Button, { onclick, children: text('Save') });
		await user.tab();
		expect(screen.getByRole('button')).toHaveFocus();
		await user.keyboard('{Enter}');
		await user.keyboard(' ');
		expect(onclick).toHaveBeenCalledTimes(2);
	});

	it('is dimmed and inert when disabled', async () => {
		const onclick = vi.fn();
		render(Button, { disabled: true, onclick, children: text('Save') });
		const button = screen.getByRole('button');
		expect(button).toBeDisabled();
		expect(button).toHaveClass('opacity-40', 'cursor-not-allowed');
		await userEvent.click(button);
		expect(onclick).not.toHaveBeenCalled();
	});
});
