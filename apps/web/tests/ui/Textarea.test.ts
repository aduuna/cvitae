import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import Textarea from '#lib/components/ui/Textarea.svelte';

describe('Textarea', () => {
	it('is labelled and accepts multi-line text', async () => {
		render(Textarea, { label: 'Job description' });
		const area = screen.getByLabelText('Job description');
		expect(area.tagName).toBe('TEXTAREA');
		expect(area).toHaveAttribute('rows', '4');
		await userEvent.type(area, 'Line one{Enter}Line two');
		expect(area).toHaveValue('Line one\nLine two');
	});

	it('shows an error and links it', () => {
		render(Textarea, { label: 'Summary', error: 'Add a summary.' });
		const area = screen.getByLabelText('Summary');
		expect(area).toHaveAttribute('aria-invalid', 'true');
		expect(area).toHaveClass('border-danger');
		expect(area).toHaveAccessibleDescription('Add a summary.');
	});
});
