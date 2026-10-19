import { describe, expect, it } from 'vitest';
import { fitLines, formatDate, matchOption, monthSpellings, pick } from '../src/content/values.ts';

const option = (text: string, value = text) => ({ value, text });

describe('matchOption', () => {
	const countries = [
		option('Choose a country', ''),
		option('Guinea', 'GN'),
		option('Guinea-Bissau', 'GW'),
		option('United Kingdom of Great Britain and Northern Ireland', 'GB'),
		option('United States of America', 'US'),
		option('United States Minor Outlying Islands', 'UM')
	];

	it('prefers an exact match, trying each spelling in turn', () => {
		expect(matchOption(countries, ['United States', 'US'])?.value).toBe('US');
		expect(matchOption(countries, ['Guinea'])?.value).toBe('GN');
	});

	it('falls back to an option that starts with the spelling', () => {
		expect(matchOption(countries, ['United Kingdom'])?.value).toBe('GB');
	});

	it('matches whole words inside an option', () => {
		const degrees = [option('Select'), option("Bachelor's Degree (BA, BSc)"), option('Masters')];
		expect(matchOption(degrees, ['Masters'])?.text).toBe('Masters');
		expect(matchOption(degrees, ['BSc'])).toBeNull();
		expect(matchOption(degrees, ['bachelor s'])).toBeNull();
		expect(matchOption(degrees, ["Bachelor's"])?.text).toBe("Bachelor's Degree (BA, BSc)");
	});

	it('never picks the placeholder option', () => {
		expect(matchOption([option('Select one', ''), option('Please choose')], ['select'])).toBeNull();
	});
});

describe('formatDate', () => {
	const base = { type: 'text', placeholder: '', part: null, options: null } as const;
	const march = { year: 2021, month: 3 };

	it('writes what the field expects', () => {
		expect(formatDate({ ...base, type: 'month' }, march)?.value).toBe('2021-03');
		expect(formatDate({ ...base, type: 'date' }, march)?.value).toBe('2021-03-01');
		expect(formatDate(base, march)?.value).toBe('03/2021');
		expect(formatDate({ ...base, placeholder: 'YYYY-MM' }, march)?.value).toBe('2021-03');
		expect(formatDate({ ...base, placeholder: 'MM-YYYY' }, march)?.value).toBe('03-2021');
		expect(formatDate({ ...base, placeholder: 'MM/YY' }, march)?.value).toBe('03/21');
		expect(formatDate({ ...base, placeholder: 'Month Year' }, march)?.value).toBe('March 2021');
		expect(formatDate({ ...base, part: 'year' }, march)?.value).toBe('2021');
		expect(formatDate({ ...base, part: 'month' }, march)?.value).toBe('3');
	});

	it('picks month and year options', () => {
		const months = [option('Month', ''), option('Jan', '01'), option('Mar', '03')];
		expect(formatDate({ ...base, part: 'month', options: months }, march)).toEqual({
			value: '03',
			display: 'Mar'
		});
		const years = [option('2020'), option('2021')];
		expect(formatDate({ ...base, options: years }, march)?.value).toBe('2021');
	});

	it('does not make up a month the CV does not give', () => {
		const yearOnly = { year: 2021, month: null };
		expect(formatDate({ ...base, part: 'month' }, yearOnly)).toBeNull();
		expect(formatDate({ ...base, type: 'month' }, yearOnly)).toBeNull();
		expect(formatDate({ ...base, type: 'date' }, yearOnly)).toBeNull();
		expect(formatDate(base, yearOnly)?.value).toBe('2021');
	});
});

describe('pick', () => {
	it('uses the first spelling for a text field', () => {
		expect(pick({ options: null }, ['', 'Ghana'])).toEqual({ value: 'Ghana', display: 'Ghana' });
		expect(pick({ options: null }, [])).toBeNull();
	});
});

describe('monthSpellings', () => {
	it('lists number, padded number, name and short name', () => {
		expect(monthSpellings(9)).toEqual(['9', '09', 'September', 'Sep']);
	});
});

describe('fitLines', () => {
	it('keeps text that fits', () => {
		expect(fitLines('short', 10)).toEqual({ text: 'short', shortened: false });
		expect(fitLines('no limit', null)).toEqual({ text: 'no limit', shortened: false });
	});

	it('drops whole lines from the end', () => {
		const text = '- First bullet\n- Second bullet\n- Third bullet';
		expect(fitLines(text, 32)).toEqual({
			text: '- First bullet\n- Second bullet',
			shortened: true
		});
	});

	it('cuts a single long line at a word', () => {
		expect(fitLines('Migrated nightly batch jobs to Spark', 20)).toEqual({
			text: 'Migrated nightly',
			shortened: true
		});
	});
});
