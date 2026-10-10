import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import Input from '#lib/components/ui/Input.svelte';

describe('Input', () => {
	it('is labelled by its label', () => {
		render(Input, { label: 'Job title' });
		const input = screen.getByLabelText('Job title');
		expect(input.tagName).toBe('INPUT');
		expect(input).toHaveAttribute('type', 'text');
		expect(input).toHaveClass('h-8', 'border-line-strong', 'bg-surface');
	});

	it('accepts typing', async () => {
		render(Input, { label: 'Company' });
		const input = screen.getByLabelText('Company');
		await userEvent.type(input, 'Acme');
		expect(input).toHaveValue('Acme');
	});

	it('links help text with aria-describedby', () => {
		render(Input, { label: 'URL', help: 'Optional.' });
		expect(screen.getByLabelText('URL')).toHaveAccessibleDescription('Optional.');
	});

	it('shows an error in danger and links it', () => {
		render(Input, { label: 'Email', error: 'Enter an email address.' });
		const input = screen.getByLabelText('Email');
		expect(input).toHaveAttribute('aria-invalid', 'true');
		expect(input).toHaveClass('border-danger');
		expect(input).toHaveAccessibleDescription('Enter an email address.');
		expect(screen.getByText('Enter an email address.')).toHaveClass('text-sm', 'text-danger');
	});

	it('can be disabled', () => {
		render(Input, { label: 'Name', disabled: true });
		expect(screen.getByLabelText('Name')).toBeDisabled();
	});
});
