import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import SegmentedControl from '#lib/components/ui/SegmentedControl.svelte';

const options = [
	{ value: 'claude', label: 'Claude' },
	{ value: 'gemini', label: 'Gemini' }
];

function setup(onchange = vi.fn()) {
	render(SegmentedControl, { options, value: 'claude', label: 'AI provider', onchange });
	return {
		onchange,
		claude: screen.getByRole('radio', { name: 'Claude' }),
		gemini: screen.getByRole('radio', { name: 'Gemini' })
	};
}

describe('SegmentedControl', () => {
	it('is a labelled radio group with the selected option checked', () => {
		const { claude, gemini } = setup();
		expect(screen.getByRole('radiogroup', { name: 'AI provider' })).toBeInTheDocument();
		expect(claude).toHaveAttribute('aria-checked', 'true');
		expect(claude).toHaveClass('bg-surface', 'shadow-page');
		expect(gemini).toHaveAttribute('aria-checked', 'false');
	});

	it('selects on click', async () => {
		const { gemini, onchange } = setup();
		await userEvent.click(gemini);
		expect(gemini).toHaveAttribute('aria-checked', 'true');
		expect(onchange).toHaveBeenCalledWith('gemini');
	});

	it('uses a roving tabindex and arrow keys that wrap', async () => {
		const user = userEvent.setup();
		const { claude, gemini, onchange } = setup();
		expect(claude).toHaveAttribute('tabindex', '0');
		expect(gemini).toHaveAttribute('tabindex', '-1');
		await user.tab();
		expect(claude).toHaveFocus();
		await user.keyboard('{ArrowRight}');
		expect(gemini).toHaveFocus();
		expect(gemini).toHaveAttribute('aria-checked', 'true');
		await user.keyboard('{ArrowRight}');
		expect(claude).toHaveFocus();
		expect(claude).toHaveAttribute('aria-checked', 'true');
		await user.keyboard('{ArrowLeft}');
		expect(gemini).toHaveFocus();
		expect(onchange).toHaveBeenLastCalledWith('gemini');
	});

	it('does not change when disabled', async () => {
		render(SegmentedControl, { options, value: 'claude', label: 'Mode', disabled: true });
		await userEvent.click(screen.getByRole('radio', { name: 'Gemini' }));
		expect(screen.getByRole('radio', { name: 'Claude' })).toHaveAttribute('aria-checked', 'true');
	});
});
