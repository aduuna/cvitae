import { describe, expect, it } from 'vitest';
import { scan } from '../src/content/fields.ts';
import { looksLikeApplication, planFill, valueFor } from '../src/content/plan.ts';
import type { Assignment } from '../src/content/types.ts';
import { field, loadFixture, sampleData } from './helpers.ts';

/** label = display, for compact assertions. */
function shown(assignments: Assignment[]): string[] {
	return assignments.map((a) => `${a.label} = ${a.display.split('\n')[0]}`);
}

describe('planFill', () => {
	it('fills the new Greenhouse form from the sample profile', () => {
		loadFixture('greenhouse-new');

		const plan = planFill(scan().fields, sampleData());

		expect(shown(plan.assignments)).toEqual([
			'First Name = Ama',
			'Last Name = Owusu-Mensah',
			'Email = ama@example.com',
			'Country = United Kingdom',
			'Phone = +44 20 7946 0958',
			'Location (City) = London, UK',
			'Company name = Northwind Consulting',
			'Title = Lead data engineer',
			'Start date month = March',
			'Start date year = 2021',
			// A current role: no end date, and the box is ticked.
			'Current role = Yes',
			'School = University of Ghana',
			'Degree = BSc Computer Science',
			'Discipline = Computer Science',
			'End date year = 2015',
			'LinkedIn Profile = https://www.linkedin.com/in/example'
		]);
		expect(plan.experience).toEqual({ slots: 1, total: 3 });
		expect(plan.education).toEqual({ slots: 1, total: 1 });
		expect(plan.assignments.every((a) => a.include)).toBe(true);
		expect(plan.assignments.find((a) => a.kind === 'location.country')?.needsChoice).toBe(true);
	});

	it('fills each Workday work experience from the matching role', () => {
		loadFixture('workday');

		const plan = planFill(scan().fields, sampleData());
		const second = plan.assignments.filter((a) => a.group === 1 && a.kind.startsWith('experience'));

		expect(shown(second)).toEqual([
			'Job Title = Data engineer',
			'Company = Brightline Analytics',
			'Location = Accra, Ghana',
			'Month = 9',
			'Year = 2017',
			'Month = 2',
			'Year = 2021',
			"Role Description = - Built the company's first warehouse on BigQuery, consolidating 12 source systems."
		]);
		// The second role is not current, and its box is not ticked: nothing to change there.
		expect(second.some((a) => a.kind === 'experience.current')).toBe(false);
	});

	it('matches lists and respects limits on the careers form', () => {
		loadFixture('careers');

		const plan = planFill(scan().fields, sampleData());
		const by = (label: string) => plan.assignments.find((a) => a.label === label);

		expect(by('Country')).toMatchObject({
			value: 'GB',
			display: 'United Kingdom of Great Britain and Northern Ireland'
		});
		// The CV gives no region, and no middle name: those fields are left out.
		expect(by('State / Province')).toBeUndefined();
		expect(by('Middle name')).toBeUndefined();
		expect(by('Degree')).toMatchObject({ value: 'ba', display: "Bachelor's Degree" });
		expect(by('From')?.value).toBe('2021-03');
		expect(by('To')).toBeUndefined();
		expect(by('Graduation date')?.value).toBe('2015-06-01');
		expect(by('Duties and achievements')).toMatchObject({ shortened: true });
		expect(by('Duties and achievements')!.value.length).toBeLessThanOrEqual(120);
		// A field with a value is planned unticked, so the user can choose to replace it.
		expect(by('Email address')).toMatchObject({ include: false, filled: true });
		expect(by('Skills')?.value).toMatch(/^Python, SQL, Scala, C#, Spark/);
	});

	it('leaves a list alone when no option matches', () => {
		const country = field({
			kind: 'location.country',
			options: [
				{ value: '', text: 'Select' },
				{ value: 'FR', text: 'France' }
			]
		});

		expect(valueFor(country, sampleData())).toBeNull();
	});

	it('skips roles the profile does not have', () => {
		const third = field({ kind: 'experience.company', group: 5 });

		expect(valueFor(third, sampleData())).toBeNull();
	});

	it('unticks a current-role box for a past role only when it is ticked', () => {
		const data = sampleData();
		const box = field({ kind: 'experience.current', type: 'checkbox', group: 1 });

		expect(planFill([box], data).assignments).toEqual([]);
		const ticked = planFill([{ ...box, filled: true }], data).assignments[0];
		expect(ticked).toMatchObject({ value: 'false', display: 'No', include: false });
	});
});

describe('looksLikeApplication', () => {
	it('needs contact fields, or a CV upload with a couple of fields', () => {
		const page = (kinds: string[], files = 0) => ({
			url: '',
			title: '',
			fields: kinds.map((kind) => field({ kind: kind as never })),
			files: Array.from({ length: files }, (_, i) => ({ id: `u${i}`, label: 'CV', hasFile: false }))
		});

		expect(looksLikeApplication(page(['email', 'name.full']))).toBe(true);
		expect(looksLikeApplication(page(['email']))).toBe(false);
		expect(looksLikeApplication(page(['link.github', 'skills'], 1))).toBe(true);
		expect(looksLikeApplication(page(['location.city']))).toBe(false);
	});
});
