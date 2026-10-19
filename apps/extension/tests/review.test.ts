import { describe, expect, it } from 'vitest';
import { scan } from '../src/content/fields.ts';
import { dates, detailGroups } from '../src/sidepanel/details.ts';
import { grouped, review } from '../src/sidepanel/review.ts';
import { loadFixture, sampleData } from './helpers.ts';

describe('review', () => {
	it('groups rows by where they come from and says what to watch for', () => {
		loadFixture('greenhouse-new');
		const data = sampleData();

		const { rows, notes } = review(
			[{ frameId: 0, scan: scan() }],
			data,
			'Data engineering profile'
		);

		expect(grouped(rows, data).map((g) => [g.title, g.rows.length])).toEqual([
			['Your details', 6],
			['Role 1: Northwind Consulting', 5],
			['School 1: University of Ghana', 4],
			['Links', 1]
		]);
		expect(rows.find((r) => r.kind === 'experience.start')?.editable).toBe(false);
		expect(rows.find((r) => r.kind === 'name.first')?.editable).toBe(true);
		expect(notes).toEqual([
			'The form has room for 1 of your 3 roles. Add another role in the form, then fill again.',
			'5 fields offer a list as you type. Pick the right entry after filling.',
			'Your Data engineering profile has 1 placeholder in square brackets. Replace it with real details before you submit.'
		]);
	});

	it('mentions fields that have a value and texts that were shortened', () => {
		loadFixture('careers');

		const { notes } = review([{ frameId: 3, scan: scan() }], sampleData(), 'CV');

		expect(notes).toContain('1 field has a value already and is left as it is. Tick to replace.');
		expect(notes).toContain('1 text was shortened to fit the field.');
	});
});

describe('details', () => {
	it('lists what to copy, role by role', () => {
		const groups = detailGroups(sampleData());

		expect(groups.map((g) => g.title)).toEqual([
			'Your details',
			'Links',
			'Lead data engineer at Northwind Consulting',
			'Data engineer at Brightline Analytics',
			'Software engineer at Kente Labs',
			'University of Ghana'
		]);
		expect(groups[2]?.items.find((i) => i.label === 'Dates')?.value).toBe('Mar 2021 to present');
		// Empty values are left out.
		expect(groups[1]?.items.map((i) => i.label)).toEqual(['LinkedIn', 'GitHub']);
	});

	it('writes dates as a reader expects', () => {
		expect(dates({ year: 2015, month: 6 }, { year: 2017, month: 8 })).toBe('Jun 2015 to Aug 2017');
		expect(dates({ year: 2015, month: null }, null)).toBe('2015');
		expect(dates(null, null, true)).toBe('present');
	});
});
