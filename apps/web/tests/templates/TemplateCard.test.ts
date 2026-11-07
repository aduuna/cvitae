import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import TemplateCard from '#lib/components/templates/TemplateCard.svelte';
import type { TemplateMeta } from '#lib/cv/types.ts';

const SLATE: TemplateMeta = {
	id: 'u-aaaaaaaaa2',
	name: 'Slate',
	description: 'Navy rules and tight spacing.',
	paper_sizes: ['a4'],
	target_pages: 1,
	custom: true
};
const PAGE = '<svg xmlns="http://www.w3.org/2000/svg" width="595pt" height="842pt"></svg>';

function card(props: Partial<Parameters<typeof render<typeof TemplateCard>>[1]> = {}) {
	const onmakedefault = vi.fn();
	render(TemplateCard, {
		template: SLATE,
		preview: PAGE,
		isDefault: false,
		busy: false,
		saving: false,
		onmakedefault,
		...props
	} as never);
	return { onmakedefault };
}

describe('TemplateCard', () => {
	it('shows the live preview, the name, the description and Set as default', async () => {
		const { onmakedefault } = card();

		expect(screen.getByRole('img', { name: 'Preview of the Slate template' })).toBeVisible();
		expect(screen.getByRole('heading', { level: 3, name: 'Slate' })).toBeVisible();
		expect(screen.getByText('Navy rules and tight spacing.')).toBeVisible();
		await userEvent.click(screen.getByRole('button', { name: 'Set as default' }));
		expect(onmakedefault).toHaveBeenCalledOnce();
	});

	it('marks the default and has nothing to set', () => {
		card({ isDefault: true });

		expect(screen.getByText('Default')).toBeVisible();
		expect(screen.queryByRole('button', { name: 'Set as default' })).toBeNull();
	});

	it('shows a placeholder while the preview renders and a message when it cannot', () => {
		const { unmount } = render(TemplateCard, {
			template: SLATE,
			preview: undefined,
			isDefault: false,
			busy: false,
			saving: false,
			onmakedefault: vi.fn()
		});
		expect(screen.queryByRole('img')).toBeNull();
		expect(screen.queryByText('The preview could not be rendered.')).toBeNull();
		unmount();

		card({ preview: null });
		expect(screen.getByText('The preview could not be rendered.')).toBeVisible();
	});

	it('blocks Set as default while another is being saved', () => {
		card({ busy: true });

		expect(screen.getByRole('button', { name: 'Set as default' })).toBeDisabled();
	});

	it('has a menu only when given one, with rename, view source and delete', async () => {
		const onselect = vi.fn();
		card({
			menu: [
				{ label: 'Rename', icon: 'rename', onselect },
				{ label: 'View source', icon: 'view-source', onselect: vi.fn() },
				{ label: 'Delete', icon: 'delete', danger: true, onselect: vi.fn() }
			]
		});

		await userEvent.click(screen.getByRole('button', { name: 'Actions for Slate' }));
		const items = within(screen.getByRole('menu')).getAllByRole('menuitem');
		expect(items.map((item) => item.textContent?.trim())).toEqual([
			'Rename',
			'View source',
			'Delete'
		]);
		await userEvent.click(items[0]!);
		expect(onselect).toHaveBeenCalledOnce();
	});

	it('has no menu for a built-in template', () => {
		card({ template: { ...SLATE, id: 'classic', name: 'Classic', custom: false } });

		expect(screen.queryByRole('button', { name: /Actions for/ })).toBeNull();
	});
});
