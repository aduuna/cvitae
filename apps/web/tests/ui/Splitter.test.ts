import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Splitter from '#lib/components/ui/Splitter.svelte';

function setup(value = 480) {
	const onchange = vi.fn();
	render(Splitter, { value, min: 360, max: 800, step: 16, label: 'Resize edit panel', onchange });
	return { onchange, separator: screen.getByRole('separator', { name: 'Resize edit panel' }) };
}

describe('Splitter', () => {
	it('exposes a focusable vertical separator with its value', () => {
		const { separator } = setup();
		expect(separator).toHaveAttribute('aria-orientation', 'vertical');
		expect(separator).toHaveAttribute('aria-valuenow', '480');
		expect(separator).toHaveAttribute('aria-valuemin', '360');
		expect(separator).toHaveAttribute('aria-valuemax', '800');
		expect(separator).toHaveAttribute('tabindex', '0');
		expect(separator).toHaveClass('w-1', 'cursor-col-resize');
	});

	it('resizes with arrow keys, Shift for bigger steps, Home and End', async () => {
		const user = userEvent.setup();
		const { separator, onchange } = setup();
		separator.focus();
		await user.keyboard('{ArrowRight}');
		expect(separator).toHaveAttribute('aria-valuenow', '496');
		await user.keyboard('{ArrowLeft}{ArrowLeft}');
		expect(separator).toHaveAttribute('aria-valuenow', '464');
		await user.keyboard('{Shift>}{ArrowRight}{/Shift}');
		expect(separator).toHaveAttribute('aria-valuenow', '544');
		await user.keyboard('{End}');
		expect(separator).toHaveAttribute('aria-valuenow', '800');
		await user.keyboard('{Home}');
		expect(separator).toHaveAttribute('aria-valuenow', '360');
		expect(onchange).toHaveBeenLastCalledWith(360);
	});

	it('clamps to min and max', async () => {
		const user = userEvent.setup();
		const { separator } = setup(368);
		separator.focus();
		await user.keyboard('{ArrowLeft}');
		expect(separator).toHaveAttribute('aria-valuenow', '360');
	});

	it('resizes by dragging and reports when the drag ends', async () => {
		const { separator, onchange } = setup();
		await fireEvent.pointerDown(separator, { button: 0, clientX: 100, pointerId: 1 });
		await fireEvent.pointerMove(separator, { clientX: 160, pointerId: 1 });
		expect(separator).toHaveAttribute('aria-valuenow', '540');
		expect(onchange).not.toHaveBeenCalled();
		await fireEvent.pointerMove(separator, { clientX: 2000, pointerId: 1 });
		expect(separator).toHaveAttribute('aria-valuenow', '800');
		await fireEvent.pointerUp(separator, { pointerId: 1 });
		expect(onchange).toHaveBeenCalledWith(800);
	});
});
