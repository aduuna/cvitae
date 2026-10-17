import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import Select from '#lib/components/ui/Select.svelte';

const options = [
	{ value: 'classic', label: 'Classic' },
	{ value: 'compact', label: 'Compact' },
	{ value: 'modern', label: 'Modern', disabled: true }
];

describe('Select', () => {
	it('renders the options under its label', () => {
		render(Select, { label: 'Template', options, value: 'classic' });
		const select = screen.getByLabelText('Template');
		expect(select).toHaveValue('classic');
		expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
			'Classic',
			'Compact',
			'Modern'
		]);
		expect(screen.getByRole('option', { name: 'Modern' })).toBeDisabled();
		expect(select.parentElement?.querySelector('[data-icon="chevron-down"]')).not.toBeNull();
	});

	it('changes value with the keyboard and pointer', async () => {
		render(Select, { label: 'Template', options, value: 'classic' });
		const select = screen.getByLabelText('Template');
		await userEvent.selectOptions(select, 'compact');
		expect(select).toHaveValue('compact');
	});

	it('shows an error and links it', () => {
		render(Select, { label: 'Template', options, error: 'Choose a template.' });
		const select = screen.getByLabelText('Template');
		expect(select).toHaveAttribute('aria-invalid', 'true');
		expect(select).toHaveAccessibleDescription('Choose a template.');
	});

	it('keeps help shown elsewhere in its description, next to its own', () => {
		render(Select, {
			label: 'Template',
			options,
			help: 'Used for new CVs.',
			'aria-describedby': 'row-help'
		});
		const ids = screen.getByLabelText('Template').getAttribute('aria-describedby')?.split(' ');
		expect(ids).toHaveLength(2);
		expect(ids).toContain('row-help');
	});
});
