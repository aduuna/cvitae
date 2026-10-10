import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import ChangesPanel from '#lib/components/tailor/ChangesPanel.svelte';
import GapsPanel from '#lib/components/tailor/GapsPanel.svelte';

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

describe('GapsPanel', () => {
	it('lists placeholders and missing keywords with the honesty note', () => {
		render(GapsPanel, {
			placeholders: [{ text: 'number of analysts', bullet_id: 'b' }],
			missingKeywords: ['Snowflake', 'Kubernetes']
		});

		expect(screen.getByText('number of analysts')).toHaveClass('bg-placeholder');
		expect(screen.getByText(/Only add these if they are true\./)).toBeVisible();
		expect(screen.getAllByRole('listitem').map((li) => li.textContent)).toEqual([
			'number of analysts',
			'Snowflake',
			'Kubernetes'
		]);
	});

	it('says when there is nothing to do', () => {
		render(GapsPanel, { placeholders: [], missingKeywords: [] });

		expect(screen.getByText('Nothing to fill in.')).toBeVisible();
		expect(screen.getByText("Your profile covers the job's keywords.")).toBeVisible();
	});
});
