import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Menu, { type MenuItem } from '#lib/components/ui/Menu.svelte';

function setup() {
	const duplicate = vi.fn();
	const rename = vi.fn();
	const remove = vi.fn();
	const items: MenuItem[] = [
		{ label: 'Duplicate', icon: 'duplicate', shortcut: 'Ctrl+D', onselect: duplicate },
		{ label: 'Rename', onselect: rename },
		{ label: 'Archive', disabled: true, onselect: vi.fn() },
		{ label: 'Delete', icon: 'delete', danger: true, onselect: remove }
	];
	const user = userEvent.setup();
	render(Menu, { items, label: 'Actions for Backend CV' });
	const trigger = screen.getByRole('button', { name: 'Actions for Backend CV' });
	return { user, trigger, duplicate, rename, remove };
}

describe('Menu', () => {
	it('starts closed with popup semantics on the trigger', () => {
		const { trigger } = setup();
		expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
		expect(trigger).toHaveAttribute('aria-expanded', 'false');
		expect(screen.queryByRole('menu')).toBeNull();
	});

	it('opens on click and focuses the first item', async () => {
		const { user, trigger } = setup();
		await user.click(trigger);
		expect(trigger).toHaveAttribute('aria-expanded', 'true');
		expect(screen.getByRole('menu')).toHaveClass('shadow-pop');
		expect(screen.getByRole('menuitem', { name: /Duplicate/ })).toHaveFocus();
		expect(screen.getByText('Ctrl+D')).toHaveClass('text-xs', 'text-fg-muted');
		expect(screen.getByRole('menuitem', { name: 'Delete' })).toHaveClass('text-danger');
	});

	it('navigates with arrows, skipping disabled items and wrapping', async () => {
		const { user, trigger } = setup();
		trigger.focus();
		await user.keyboard('{ArrowDown}');
		expect(screen.getByRole('menuitem', { name: /Duplicate/ })).toHaveFocus();
		await user.keyboard('{ArrowDown}');
		expect(screen.getByRole('menuitem', { name: 'Rename' })).toHaveFocus();
		await user.keyboard('{ArrowDown}');
		expect(screen.getByRole('menuitem', { name: 'Delete' })).toHaveFocus();
		await user.keyboard('{ArrowDown}');
		expect(screen.getByRole('menuitem', { name: /Duplicate/ })).toHaveFocus();
		await user.keyboard('{ArrowUp}');
		expect(screen.getByRole('menuitem', { name: 'Delete' })).toHaveFocus();
		await user.keyboard('{Home}');
		expect(screen.getByRole('menuitem', { name: /Duplicate/ })).toHaveFocus();
	});

	it('opens on ArrowUp with the last item focused', async () => {
		const { user, trigger } = setup();
		trigger.focus();
		await user.keyboard('{ArrowUp}');
		expect(screen.getByRole('menuitem', { name: 'Delete' })).toHaveFocus();
	});

	it('selects with Enter, closes and returns focus', async () => {
		const { user, trigger, rename } = setup();
		await user.click(trigger);
		await user.keyboard('{ArrowDown}{Enter}');
		expect(rename).toHaveBeenCalledOnce();
		expect(screen.queryByRole('menu')).toBeNull();
		expect(trigger).toHaveFocus();
	});

	it('selects with a click', async () => {
		const { user, trigger, remove } = setup();
		await user.click(trigger);
		await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
		expect(remove).toHaveBeenCalledOnce();
	});

	it('closes with Escape and returns focus to the trigger', async () => {
		const { user, trigger, duplicate } = setup();
		await user.click(trigger);
		await user.keyboard('{Escape}');
		expect(screen.queryByRole('menu')).toBeNull();
		expect(trigger).toHaveFocus();
		expect(duplicate).not.toHaveBeenCalled();
	});

	it('closes on a pointer press outside', async () => {
		const { user, trigger } = setup();
		await user.click(trigger);
		await fireEvent.pointerDown(document.body);
		expect(screen.queryByRole('menu')).toBeNull();
	});
});

describe('Menu with a text trigger', () => {
	it('opens from a labelled button', async () => {
		const add = vi.fn();
		const user = userEvent.setup();
		render(Menu, {
			items: [{ label: 'Projects', onselect: add }],
			text: 'Add section',
			icon: 'new'
		});

		const trigger = screen.getByRole('button', { name: 'Add section' });
		expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
		expect(trigger.querySelector('[data-icon="new"]')).not.toBeNull();
		await user.click(trigger);
		await user.click(screen.getByRole('menuitem', { name: 'Projects' }));

		expect(add).toHaveBeenCalledOnce();
		expect(trigger).toHaveFocus();
	});
});

describe('Menu placement', () => {
	it('opens below by default and above when asked', async () => {
		const user = userEvent.setup();
		const items: MenuItem[] = [{ label: 'Sign out', onselect: vi.fn() }];
		const { unmount } = render(Menu, { items, label: 'Below' });
		await user.click(screen.getByRole('button', { name: 'Below' }));
		expect(screen.getByRole('menu')).toHaveClass('top-full');
		unmount();

		render(Menu, { items, label: 'Above', placement: 'top' });
		await user.click(screen.getByRole('button', { name: 'Above' }));
		expect(screen.getByRole('menu')).toHaveClass('bottom-full');
		expect(screen.getByRole('menu')).not.toHaveClass('top-full');
	});
});
