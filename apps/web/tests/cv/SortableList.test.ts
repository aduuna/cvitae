import { createEvent, fireEvent, render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import SortableHarness from './harness/SortableHarness.svelte';

function rows() {
	return [
		{
			id: 'a',
			text: 'Acme',
			children: [
				{ id: 'a1', text: 'one' },
				{ id: 'a2', text: 'two' }
			]
		},
		{ id: 'b', text: 'Brightline', children: [] },
		{ id: 'c', text: 'Kente', children: [] }
	];
}

function values(label: RegExp) {
	return screen
		.getAllByRole('textbox', { name: label })
		.map((el) => (el as HTMLInputElement).value);
}

describe('SortableList', () => {
	it('moves the focused item with Alt+Down and Alt+Up, keeping focus', async () => {
		const user = userEvent.setup();
		const { component } = render(SortableHarness, { initial: rows() });
		const ids = () => component.current().map((item) => item.id);

		await user.click(screen.getByRole('textbox', { name: 'Role 1' }));
		await user.keyboard('{Alt>}{ArrowDown}{/Alt}');

		expect(values(/^Role \d$/)).toEqual(['Brightline', 'Acme', 'Kente']);
		expect(ids()).toEqual(['b', 'a', 'c']);
		expect(screen.getByRole('textbox', { name: 'Role 2' })).toHaveFocus();
		expect(screen.getByText('Moved role to position 2 of 3.')).toBeInTheDocument();

		await user.keyboard('{Alt>}{ArrowUp}{/Alt}{Alt>}{ArrowUp}{/Alt}');
		expect(values(/^Role \d$/)).toEqual(['Acme', 'Brightline', 'Kente']);
	});

	it('moves the innermost list only', async () => {
		const user = userEvent.setup();
		const { component } = render(SortableHarness, { initial: rows() });
		const ids = () => component.current().map((item) => item.id);

		await user.click(screen.getByRole('textbox', { name: 'Acme bullet 1' }));
		await user.keyboard('{Alt>}{ArrowDown}{/Alt}');

		expect(component.current()[0]?.children.map((child) => child.id)).toEqual(['a2', 'a1']);
		expect(ids()).toEqual(['a', 'b', 'c']);
	});

	it('ignores arrows without Alt', async () => {
		const user = userEvent.setup();
		const { component } = render(SortableHarness, { initial: rows() });
		const ids = () => component.current().map((item) => item.id);

		await user.click(screen.getByRole('textbox', { name: 'Role 1' }));
		await user.keyboard('{ArrowDown}');

		expect(ids()).toEqual(['a', 'b', 'c']);
	});

	it('labels each drag handle with its position', () => {
		render(SortableHarness, { initial: rows() });

		const roles = screen.getByRole('list', { name: 'Roles' });
		const handle = within(roles).getByRole('button', { name: 'Move role 3 of 3' });
		expect(handle).toHaveAttribute('draggable', 'true');
	});

	it('reorders by dragging a handle onto another item', async () => {
		const { component } = render(SortableHarness, { initial: rows() });
		const ids = () => component.current().map((item) => item.id);
		const transfer = { setData: () => {}, setDragImage: () => {}, effectAllowed: '' };

		const handle = screen.getByRole('button', { name: 'Move role 1 of 3' });
		const target = screen.getByRole('textbox', { name: 'Role 3' }).closest('li')!;
		await fireEvent.dragStart(handle, { dataTransfer: transfer });
		const over = createEvent.dragOver(target, { dataTransfer: transfer });
		Object.defineProperty(over, 'clientY', { value: 10 });
		await fireEvent(target, over);
		expect(target.querySelector('[data-drop-indicator="after"]')).not.toBeNull();
		await fireEvent.drop(target, { dataTransfer: transfer });

		expect(ids()).toEqual(['b', 'c', 'a']);
		expect(document.querySelector('[data-drop-indicator]')).toBeNull();
	});
});
