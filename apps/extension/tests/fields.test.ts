import { describe, expect, it } from 'vitest';
import { cleanLabel, element, scan } from '../src/content/fields.ts';
import { loadFixture, summary } from './helpers.ts';

describe('scan', () => {
	it('reads the classic Greenhouse form and leaves its questions alone', () => {
		loadFixture('greenhouse');

		const page = scan();

		expect(summary(page)).toEqual([
			'First Name: name.first',
			'Last Name: name.last',
			'Email: email',
			'Phone: phone',
			'LinkedIn Profile: link.linkedin',
			'Website: link.website'
		]);
		// The CV upload, but not the cover letter one; hidden inputs count, sites hide them.
		expect(page.files.map((f) => f.label)).toEqual(['Resume/CV']);
	});

	it('reads the new Greenhouse form with its employment and education sections', () => {
		loadFixture('greenhouse-new');

		const page = scan();

		expect(summary(page)).toEqual([
			'First Name: name.first',
			'Last Name: name.last',
			'Email: email',
			'Country: location.country',
			'Phone: phone',
			'Location (City): location.full',
			'Company name: experience.company',
			'Title: experience.title',
			'Start date month: experience.start (month)',
			'Start date year: experience.start (year)',
			'End date month: experience.end (month)',
			'End date year: experience.end (year)',
			'Current role: experience.current',
			'School: education.school',
			'Degree: education.degree',
			'Discipline: education.field',
			'End date year: education.end (year)',
			'LinkedIn Profile: link.linkedin'
		]);
		const country = page.fields.find((f) => f.kind === 'location.country');
		expect(country?.needsChoice).toBe(true);
	});

	it('reads Lever, whose labels wrap the field', () => {
		loadFixture('lever');

		const page = scan();

		expect(summary(page)).toEqual([
			'Full name: name.full',
			'Email: email',
			'Phone: phone',
			'Current location: location.full',
			'Current company: current.company',
			'LinkedIn URL: link.linkedin',
			'Twitter URL: link.twitter',
			'GitHub URL: link.github',
			'Portfolio URL: link.website'
		]);
		expect(page.files.map((f) => f.label)).toEqual(['Resume/CV']);
	});

	it('reads Workday, counting each work experience as its own group', () => {
		loadFixture('workday');

		const page = scan();

		expect(summary(page)).toEqual([
			'Job Title: experience.title',
			'Company: experience.company',
			'Location: experience.location',
			'I currently work here: experience.current',
			'Month: experience.start (month)',
			'Year: experience.start (year)',
			'Month: experience.end (month)',
			'Year: experience.end (year)',
			'Role Description: experience.description',
			'Job Title: experience.title #1',
			'Company: experience.company #1',
			'Location: experience.location #1',
			'I currently work here: experience.current #1',
			'Month: experience.start (month) #1',
			'Year: experience.start (year) #1',
			'Month: experience.end (month) #1',
			'Year: experience.end (year) #1',
			'Role Description: experience.description #1',
			'School or University: education.school',
			'Field of Study: education.field',
			'LinkedIn: link.linkedin'
		]);
	});

	it('reads Ashby and skips what the profile cannot answer', () => {
		loadFixture('ashby');

		const page = scan();

		expect(summary(page)).toEqual([
			'Name: name.full',
			'Email: email',
			'LinkedIn Profile: link.linkedin',
			'GitHub: link.github',
			'Where are you located?: location.full'
		]);
		expect(page.files).toHaveLength(1);
	});

	it('reads a custom careers form', () => {
		loadFixture('careers');

		const page = scan();

		expect(summary(page)).toEqual([
			'First name: name.first',
			'Middle name: name.middle',
			'Last name: name.last',
			'Email address: email',
			'Mobile number: phone',
			'City: location.city',
			'State / Province: location.region',
			'Country: location.country',
			'Professional headline: headline',
			'Professional summary: summary',
			'Skills: skills',
			'Personal website: link.website',
			'Employer: experience.company',
			'Position: experience.title',
			'From: experience.start',
			'To: experience.end',
			'I currently work here: experience.current',
			'Duties and achievements: experience.description',
			'University: education.school',
			'Degree: education.degree',
			'Major: education.field',
			'Graduation date: education.end'
		]);
		const email = page.fields.find((f) => f.kind === 'email');
		expect(email?.filled).toBe(true);
		expect(page.fields.find((f) => f.kind === 'experience.description')?.maxLength).toBe(120);
	});

	it('keeps an id per element across scans', () => {
		loadFixture('lever');
		const first = scan();
		document.querySelector('form')?.prepend(document.createElement('input'));

		const second = scan();

		expect(second.fields.map((f) => f.id)).toEqual(first.fields.map((f) => f.id));
		expect(element(first.fields[0]!.id)).toBe(document.querySelector('input[name="name"]'));
	});

	it('skips hidden, disabled and read-only fields', () => {
		document.body.innerHTML = `
			<label for="a">Email</label><input id="a" hidden>
			<label for="b">Email</label><input id="b" disabled>
			<label for="c">Email</label><input id="c" readonly>
			<div aria-hidden="true"><label for="d">Email</label><input id="d"></div>
			<label for="e">Email</label><input id="e">`;

		expect(scan().fields.map((f) => element(f.id)?.id)).toEqual(['e']);
	});

	it('finds fields inside open shadow roots', () => {
		const host = document.createElement('div');
		document.body.append(host);
		host.attachShadow({ mode: 'open' }).innerHTML =
			'<label for="x">Last name</label><input id="x">';

		expect(summary(scan())).toEqual(['Last name: name.last']);
	});
});

describe('cleanLabel', () => {
	it.each([
		['First Name *', 'First Name'],
		['Resume/CV\u2731', 'Resume/CV'],
		['Phone (optional)', 'Phone'],
		['  Email:  ', 'Email']
	])('%s reads %s', (raw, clean) => {
		expect(cleanLabel(raw)).toBe(clean);
	});
});
