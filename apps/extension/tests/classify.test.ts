import { describe, expect, it } from 'vitest';
import { classify, datePart, words, type Described } from '../src/content/classify.ts';
function described(overrides: Partial<Described>): Described {
	return {
		tag: 'input',
		type: 'text',
		label: '',
		context: '',
		hints: [],
		autocomplete: '',
		placeholder: '',
		maxLength: null,
		options: null,
		filled: false,
		needsChoice: false,
		...overrides
	};
}

const kindOf = (overrides: Partial<Described>) => classify(described(overrides))?.kind ?? null;

describe('words', () => {
	it.each([
		['job_application[firstName]', 'job application first name'],
		['LinkedIn', 'linked in'],
		['urls[GitHub]', 'urls git hub'],
		['Bachelor\u2019s Degree', "bachelor's degree"],
		['R\u00e9sum\u00e9', 'resume']
	])('%s reads %s', (raw, expected) => {
		expect(words(raw)).toBe(expected);
	});
});

describe('classify', () => {
	it.each([
		[{ label: 'Given name' }, 'name.first'],
		[{ label: 'Surname' }, 'name.last'],
		[{ label: 'Middle initial' }, 'name.middle'],
		[{ label: 'Your name' }, 'name.full'],
		[{ hints: ['fname'] }, 'name.first'],
		[{ autocomplete: 'section-a family-name' }, 'name.last'],
		[{ label: 'E-mail' }, 'email'],
		[{ type: 'email', label: 'Contact' }, 'email'],
		[{ type: 'tel', label: 'Contact number' }, 'phone'],
		[{ label: 'Cell phone' }, 'phone'],
		[{ label: 'Stack Overflow profile' }, 'link.stackoverflow'],
		[{ label: 'GitLab' }, 'link.gitlab'],
		[{ label: 'X profile' }, 'link.twitter'],
		[{ label: 'Blog' }, 'link.website'],
		[{ type: 'url', label: 'Link to your work' }, 'link.website'],
		[{ label: 'Country of residence' }, 'location.country'],
		[{ label: 'Town' }, 'location.city'],
		[{ label: 'Where are you based?' }, 'location.full'],
		[{ label: 'Most recent employer' }, 'current.company'],
		[{ label: 'Current job title' }, 'current.title'],
		[{ label: 'Technologies you use' }, 'skills'],
		[{ tag: 'textarea', type: 'textarea', label: 'Tell us about yourself' }, 'summary']
	] as [Partial<Described>, string][])('%o is %s', (overrides, kind) => {
		expect(kindOf(overrides)).toBe(kind);
	});

	it.each([
		'Gender',
		'Are you a protected veteran?',
		'Disability status',
		'Pronouns',
		'Date of birth',
		'Desired salary',
		'Do you require visa sponsorship?',
		'Are you authorized to work in the US?',
		'Referral name',
		'How did you hear about us?',
		'Cover letter',
		'Years of experience',
		'Preferred first name',
		'Nationality',
		'I agree to the privacy policy',
		'Emergency contact phone'
	])('never fills "%s"', (label) => {
		expect(kindOf({ label })).toBeNull();
		expect(kindOf({ label, type: 'checkbox' })).toBeNull();
	});

	it('never fills passwords, files, radios or hidden fields', () => {
		for (const type of ['password', 'file', 'radio', 'hidden', 'submit', 'search']) {
			expect(kindOf({ type, label: 'Email' })).toBeNull();
		}
	});

	it('reads a field by its section', () => {
		const experience = { context: 'Work experience' };
		expect(kindOf({ ...experience, label: 'Company' })).toBe('experience.company');
		expect(kindOf({ ...experience, label: 'Location' })).toBe('experience.location');
		expect(kindOf({ ...experience, label: 'Start date', type: 'date' })).toBe('experience.start');
		expect(kindOf({ ...experience, label: 'End date' })).toBe('experience.end');
		expect(kindOf({ ...experience, label: 'Still working here', type: 'checkbox' })).toBe(
			'experience.current'
		);
		const education = { context: 'Education' };
		expect(kindOf({ ...education, label: 'Institution name' })).toBe('education.school');
		expect(kindOf({ ...education, label: 'Area of study' })).toBe('education.field');
		expect(kindOf({ ...education, label: 'Qualification' })).toBe('education.degree');
		expect(kindOf({ ...education, label: 'GPA' })).toBeNull();
		// Outside a section a company is the current one, and a bare date is not a role's.
		expect(kindOf({ label: 'Company' })).toBe('current.company');
		expect(kindOf({ label: 'Start date', type: 'date' })).toBeNull();
	});

	it('does not take a generic field name for a job title', () => {
		// Greenhouse names every custom question job_application[...].
		const question = {
			context: 'Experience',
			label: 'Which databases have you run in production?',
			hints: ['job_application[answers_attributes][4][text_value]']
		};
		expect(kindOf(question)).toBeNull();
		expect(kindOf({ ...question, tag: 'textarea', type: 'textarea' })).toBeNull();
	});

	it('leaves a street address alone but reads the country next to it', () => {
		expect(kindOf({ label: 'Address line 1', hints: ['addressSection_addressLine1'] })).toBeNull();
		expect(kindOf({ label: 'Country', hints: ['addressSection_countryRegion'] })).toBe(
			'location.country'
		);
		expect(kindOf({ label: 'Country code', hints: ['phone'] })).toBeNull();
	});

	it('takes a graduation date for the end of education wherever it is', () => {
		expect(classify(described({ label: 'Graduation year', maxLength: 4 }))).toEqual({
			kind: 'education.end',
			part: 'year'
		});
	});
});

describe('datePart', () => {
	const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August'];
	const allMonths = [...months, 'September', 'October', 'November', 'December'];

	it('reads month and year lists and inputs', () => {
		const monthList = described({
			options: [
				{ value: '', text: 'Month' },
				...allMonths.map((m, i) => ({ value: `${i + 1}`, text: m }))
			]
		});
		expect(datePart(monthList, '')).toBe('month');
		const yearList = described({
			options: [
				{ value: '', text: 'Year' },
				{ value: '2024', text: '2024' },
				{ value: '2023', text: '2023' }
			]
		});
		expect(datePart(yearList, '')).toBe('year');
		expect(datePart(described({ maxLength: 4 }), '')).toBe('year');
		expect(datePart(described({ placeholder: 'MM' }), '')).toBe('month');
		expect(datePart(described({}), 'start date')).toBeNull();
	});
});
