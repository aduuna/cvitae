import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { newSection } from '#lib/cv/factory.ts';
import type { CvContent } from '#lib/cv/types.ts';
import EditorHarness from './harness/EditorHarness.svelte';

function emptyContent(): CvContent {
	return {
		schema_version: 1,
		basics: { name: '', headline: '', email: '', phone: '', location: '', links: [] },
		summary: '',
		sections: [newSection('experience'), newSection('skills')]
	};
}

function setup(initial = emptyContent(), disabled = false) {
	const user = userEvent.setup();
	const { component } = render(EditorHarness, { initial, disabled });
	return { user, content: () => component.current() };
}

describe('CvEditor', () => {
	it('edits basics, links and the summary in place', async () => {
		const { user, content } = setup();

		await user.type(screen.getByRole('textbox', { name: 'Name' }), 'Ama');
		await user.click(screen.getByRole('button', { name: 'Add link' }));
		await user.type(screen.getByRole('textbox', { name: 'Link 1 label' }), 'GitHub');
		await user.type(screen.getByRole('textbox', { name: 'Summary' }), 'Data engineer');

		expect(content().basics.name).toBe('Ama');
		expect(content().basics.links).toEqual([{ label: 'GitHub', url: '' }]);
		expect(content().summary).toBe('Data engineer');
	});

	it('builds a role with stack, bullets and a client', async () => {
		const { user, content } = setup();
		const experience = screen.getByRole('region', { name: 'Experience' });

		await user.click(within(experience).getByRole('button', { name: 'Add role' }));
		await user.type(within(experience).getByRole('textbox', { name: 'Organisation' }), 'Acme');
		await user.type(within(experience).getByRole('textbox', { name: 'Start' }), '2021-03');
		await user.type(within(experience).getByRole('textbox', { name: 'End' }), '2023');
		await user.type(within(experience).getByRole('textbox', { name: 'Tech stack' }), 'Python, Go,');
		expect(within(experience).getByRole('textbox', { name: 'Tech stack' })).toHaveValue(
			'Python, Go,'
		);
		await user.type(within(experience).getByRole('textbox', { name: 'Bullet 1' }), 'Shipped');
		await user.click(within(experience).getByRole('button', { name: 'Add bullet' }));
		expect(within(experience).getByRole('textbox', { name: 'Bullet 2' })).toHaveFocus();
		await user.click(within(experience).getByRole('button', { name: 'Add client' }));
		await user.type(screen.getAllByRole('textbox', { name: 'Name' })[1]!, 'Harbour Bank');

		const role = () => content().sections[0]!.experience[0]!;
		expect(role().org).toBe('Acme');
		expect(role().dates).toEqual({ start: '2021-03', end: '2023' });
		expect(role().stack).toEqual(['Python', 'Go']);
		expect(role().bullets.map((bullet) => bullet.text)).toEqual(['Shipped', '']);
		expect(role().engagements[0]).toMatchObject({ name: 'Harbour Bank', label: 'Client' });
		expect(within(experience).getByText('Client: Harbour Bank')).toBeInTheDocument();

		await user.clear(within(experience).getAllByRole('textbox', { name: 'End' })[0]!);
		expect(role().dates.end).toBeNull();
		await user.click(within(experience).getByRole('button', { name: 'Delete bullet 2' }));
		expect(role().bullets).toHaveLength(1);
	});

	it('normalises a list when the field loses focus', async () => {
		const { user, content } = setup();
		const skills = screen.getByRole('region', { name: 'Skills' });

		await user.click(within(skills).getByRole('button', { name: 'Add skill group' }));
		const field = within(skills).getByRole('textbox', { name: 'Skills' });
		await user.type(field, ' SQL ,Python,');
		await user.tab();

		expect(content().sections[1]!.skills[0]!.items).toEqual(['SQL', 'Python']);
		expect(field).toHaveValue('SQL, Python');
	});

	it('adds sections from the menu and deletes empty ones at once', async () => {
		const { user, content } = setup();

		await user.click(screen.getByRole('button', { name: 'Add section' }));
		await user.click(screen.getByRole('menuitem', { name: 'Certifications' }));
		expect(content().sections.map((section) => section.kind)).toEqual([
			'experience',
			'skills',
			'certifications'
		]);

		await user.click(screen.getByRole('button', { name: 'Delete section Certifications' }));
		expect(content().sections).toHaveLength(2);
	});

	it('asks before deleting a section that has entries', async () => {
		const initial = emptyContent();
		initial.sections[1]!.skills.push({ id: 's1', label: 'Languages', items: ['Python'] });
		const { user, content } = setup(initial);

		await user.click(screen.getByRole('button', { name: 'Delete section Skills' }));
		const dialog = screen.getByRole('dialog', { name: 'Delete section' });
		expect(dialog).toHaveTextContent('The Skills section and its 1 entry will be removed.');
		await user.click(within(dialog).getByRole('button', { name: 'Delete section' }));

		expect(content().sections.map((section) => section.kind)).toEqual(['experience']);
	});

	it('reorders sections from the keyboard', async () => {
		const { user, content } = setup();

		await user.click(screen.getAllByRole('textbox', { name: 'Section title' })[0]!);
		await user.keyboard('{Alt>}{ArrowDown}{/Alt}');

		expect(content().sections.map((section) => section.kind)).toEqual(['skills', 'experience']);
	});

	it('is read-only when disabled', () => {
		setup(emptyContent(), true);

		expect(screen.getByRole('textbox', { name: 'Name' })).toBeDisabled();
		expect(screen.getByRole('button', { name: 'Add link' })).toBeDisabled();
	});
});
