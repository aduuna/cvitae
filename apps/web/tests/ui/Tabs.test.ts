import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import TabsHarness from './harness/TabsHarness.svelte';

function setup() {
	render(TabsHarness);
	return {
		preview: screen.getByRole('tab', { name: 'Preview' }),
		changes: screen.getByRole('tab', { name: 'Changes' }),
		gaps: screen.getByRole('tab', { name: 'Gaps' })
	};
}

describe('Tabs', () => {
	it('renders a labelled tab list with the active tab selected and its panel', () => {
		const { preview, changes } = setup();
		expect(screen.getByRole('tablist', { name: 'Review' })).toBeInTheDocument();
		expect(preview).toHaveAttribute('aria-selected', 'true');
		expect(preview).toHaveClass('border-accent', 'text-fg');
		expect(changes).toHaveAttribute('aria-selected', 'false');
		const tabpanel = screen.getByRole('tabpanel');
		expect(tabpanel).toHaveTextContent('Panel preview');
		expect(tabpanel).toHaveAccessibleName('Preview');
		expect(preview).toHaveAttribute('aria-controls', tabpanel.id);
	});

	it('shows an icon before the label of tabs that have one', () => {
		const { preview, changes } = setup();
		expect(changes.querySelector('svg')).not.toBeNull();
		expect(preview.querySelector('svg')).toBeNull();
	});

	it('switches on click', async () => {
		const { gaps } = setup();
		await userEvent.click(gaps);
		expect(gaps).toHaveAttribute('aria-selected', 'true');
		expect(screen.getByRole('tabpanel')).toHaveTextContent('Panel gaps');
	});

	it('moves with arrow keys, Home and End', async () => {
		const user = userEvent.setup();
		const { preview, changes, gaps } = setup();
		await user.tab();
		expect(preview).toHaveFocus();
		await user.keyboard('{ArrowRight}');
		expect(changes).toHaveFocus();
		expect(changes).toHaveAttribute('aria-selected', 'true');
		await user.keyboard('{End}');
		expect(gaps).toHaveFocus();
		await user.keyboard('{ArrowRight}');
		expect(preview).toHaveFocus();
		await user.keyboard('{ArrowLeft}');
		expect(gaps).toHaveFocus();
		await user.keyboard('{Home}');
		expect(preview).toHaveFocus();
		expect(screen.getByRole('tabpanel')).toHaveTextContent('Panel preview');
	});

	it('keeps only the selected tab in the tab order', () => {
		const { preview, changes, gaps } = setup();
		expect(preview).toHaveAttribute('tabindex', '0');
		expect(changes).toHaveAttribute('tabindex', '-1');
		expect(gaps).toHaveAttribute('tabindex', '-1');
	});
});
