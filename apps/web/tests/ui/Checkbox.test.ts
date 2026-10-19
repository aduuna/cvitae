import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import Checkbox from '#lib/components/ui/Checkbox.svelte';

describe('Checkbox', () => {
	it('is labelled by its label and toggles on click and Space', async () => {
		render(Checkbox, { label: 'Offer to fill on job sites' });
		const box = screen.getByRole('checkbox', { name: 'Offer to fill on job sites' });
		expect(box).not.toBeChecked();
		expect(box).toHaveClass('accent-accent', 'border-line-strong');

		await userEvent.click(screen.getByText('Offer to fill on job sites'));
		expect(box).toBeChecked();
		await userEvent.keyboard(' ');
		expect(box).not.toBeChecked();
	});

	it('starts checked and links help text', () => {
		render(Checkbox, { label: 'Replace', checked: true, help: 'The field has a value already.' });
		const box = screen.getByRole('checkbox', { name: 'Replace' });
		expect(box).toBeChecked();
		expect(box).toHaveAccessibleDescription('The field has a value already.');
	});

	it('can be disabled', () => {
		render(Checkbox, { label: 'Replace', disabled: true });
		expect(screen.getByRole('checkbox', { name: 'Replace' })).toBeDisabled();
	});
});
