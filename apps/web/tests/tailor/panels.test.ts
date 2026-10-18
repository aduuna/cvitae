import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ChangesPanel from '#lib/components/tailor/ChangesPanel.svelte';
import NextSteps from '#lib/components/tailor/NextSteps.svelte';
import type { TailorResult } from '#lib/cv/types.ts';

const mocks = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$app/paths', () => ({
	resolve: (route: string, params: Record<string, string> = {}) =>
		route.replace(/\[(\w+)\]/g, (_, key: string) => params[key] ?? '')
}));

const changes = [
	{
		source_id: 'b1',
		entry: 'Lead data engineer, Northwind',
		source_text: 'Lead a team of **5 engineers**.',
		text: 'Led **5 engineers** building payment pipelines.',
		rationale: 'Leads with team size.'
	},
	{
		source_id: 'b2',
		entry: 'Lead data engineer, Northwind',
		source_text: 'Kept bullet.',
		text: 'Kept bullet.',
		rationale: null
	},
	{
		source_id: 'b3',
		entry: 'Data engineer, Brightline',
		source_text: 'Built a warehouse.',
		text: 'Built the first BigQuery warehouse.',
		rationale: null
	}
];

describe('ChangesPanel', () => {
	it('groups changes by entry and shows the source above the new text', () => {
		render(ChangesPanel, { changes, dropped: [], issues: [] });

		const northwind = screen.getByRole('heading', { name: 'Lead data engineer, Northwind' })
			.parentElement as HTMLElement;
		expect(within(northwind).getAllByRole('listitem')).toHaveLength(2);
		expect(within(northwind).getByText('Leads with team size.')).toBeVisible();
		expect(within(northwind).getByText('Kept as written')).toBeVisible();
		const original = within(northwind).getByText('Lead a team of', { exact: false });
		expect(original).toHaveClass('text-fg-muted');
		expect(screen.getByRole('heading', { name: 'Data engineer, Brightline' })).toBeVisible();
		expect(screen.queryByText(/Corrected by the fact check/)).toBeNull();
	});

	it('lists fact check corrections and left-out bullets', () => {
		render(ChangesPanel, {
			changes: [],
			dropped: [
				{ source_id: 'b9', entry: 'Software engineer, Kente Labs', text: 'Shipped **1.2M**.' }
			],
			issues: [
				{
					kind: 'new_number',
					message: 'The number 40 is not in your profile. Check it before using this CV.',
					bullet_id: 'x',
					value: '40'
				}
			]
		});

		expect(
			screen.getByRole('heading', { name: /Corrected by the fact check \(1\)/ })
		).toBeVisible();
		expect(screen.getByText(/The number 40 is not in your profile/)).toBeVisible();
		expect(screen.getByRole('heading', { name: 'Left out (1)' })).toBeVisible();
		expect(screen.getByText('Software engineer, Kente Labs:')).toBeVisible();
	});
});

function result(overrides: Partial<TailorResult> = {}): TailorResult {
	return {
		document: { id: 'd1', profile_id: 'p1' },
		job: { id: 'j1', title: 'Data engineer', company: 'Agoda' },
		ai_model: 'mimo-flash',
		provider: 'mimo',
		model: 'mimo-v2.6-flash',
		issues: [{ kind: 'new_skill', message: 'Removed Kubernetes: it is not in your profile.' }],
		changes,
		dropped: [{ source_id: 'b9', entry: 'Data engineer, Brightline', text: 'Old bullet.' }],
		placeholders: [
			{ text: 'number of analysts', bullet_id: 'b1' },
			{ text: 'latency', bullet_id: 'b3' }
		],
		missing_keywords: Array.from({ length: 12 }, (_, i) => `Keyword ${i + 1}`),
		...overrides
	} as unknown as TailorResult;
}

describe('NextSteps', () => {
	it('puts the gaps first, then the missing keywords, and folds the details away', async () => {
		const user = userEvent.setup();
		render(NextSteps, { result: result() });

		// The first headings; jsdom does not hide what a closed <details> holds.
		expect(
			screen
				.getAllByRole('heading')
				.map((h) => h.textContent?.trim())
				.slice(0, 2)
		).toEqual(['Fill in 2 gaps', 'Not in your profile (12)']);
		await user.click(screen.getByRole('button', { name: 'Fill in the editor' }));
		expect(mocks.goto).toHaveBeenLastCalledWith('/app/documents/d1');

		const keywords = () =>
			within(screen.getByRole('list', { name: 'Job keywords not in your profile' })).getAllByRole(
				'listitem'
			);
		expect(keywords()).toHaveLength(10);
		await user.click(screen.getByRole('button', { name: 'Show all 12' }));
		expect(keywords()).toHaveLength(12);
		await user.click(screen.getByRole('button', { name: 'Edit profile' }));
		expect(mocks.goto).toHaveBeenLastCalledWith('/app/profiles/p1');

		const details = screen.getByText(/^What changed:/).closest('details');
		expect(details).not.toHaveAttribute('open');
		expect(screen.getByText(/^What changed:/)).toHaveTextContent(
			'What changed: 2 reworded, 1 kept as written, 1 left out, 1 corrected by the fact check'
		);
	});

	it('says when there is nothing to fill in, and leaves out what does not apply', () => {
		render(NextSteps, { result: result({ placeholders: [], missing_keywords: [], issues: [] }) });

		expect(screen.getByRole('heading', { name: 'Nothing to fill in' })).toBeVisible();
		expect(screen.queryByRole('button', { name: 'Fill in the editor' })).toBeNull();
		expect(screen.queryByText(/Not in your profile/)).toBeNull();
		expect(screen.getByText(/^What changed:/)).toHaveTextContent(
			'What changed: 2 reworded, 1 kept as written, 1 left out'
		);
	});
});
