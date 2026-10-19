import { words } from './classify.ts';
import type { DatePart, Option, YearMonth } from './types.ts';

export const MONTH_NAMES = [
	'January',
	'February',
	'March',
	'April',
	'May',
	'June',
	'July',
	'August',
	'September',
	'October',
	'November',
	'December'
];

const PLACEHOLDER_OPTION = /^(select|choose|please|pick|none selected)\b/;

/**
 * The option a list should take for a value, trying each spelling in turn: an exact match on the
 * text or value, then an option that starts with the spelling, then one that contains it as whole
 * words. Null when nothing matches; the user then picks.
 */
export function matchOption(options: Option[], spellings: string[]): Option | null {
	const choices = options
		.map((option) => ({ option, text: words(option.text), value: words(option.value) }))
		.filter(({ text, option }) => option.value !== '' && text && !PLACEHOLDER_OPTION.test(text));
	const wanted = [...new Set(spellings.map(words).filter(Boolean))];
	for (const spelling of wanted) {
		const exact = choices.find(({ text, value }) => text === spelling || value === spelling);
		if (exact) return exact.option;
	}
	for (const spelling of wanted.filter((s) => s.length >= 3)) {
		const prefix = choices.find(({ text }) => text.startsWith(`${spelling} `));
		if (prefix) return prefix.option;
	}
	for (const spelling of wanted.filter((s) => s.length >= 4)) {
		const inside = choices.find(({ text }) => ` ${text} `.includes(` ${spelling} `));
		if (inside) return inside.option;
	}
	return null;
}

const pad = (n: number) => String(n).padStart(2, '0');

/** Spellings of a month a list might use: 3, 03, March, Mar. */
export function monthSpellings(month: number): string[] {
	const name = MONTH_NAMES[month - 1] ?? '';
	return [String(month), pad(month), name, name.slice(0, 3)];
}

export interface DateField {
	type: string;
	placeholder: string;
	part: DatePart | null;
	options: Option[] | null;
}

export interface Value {
	value: string;
	display: string;
}

/**
 * A date as the field wants it. Null when the field needs a month the CV does not give: the
 * extension fills in what the CV says and leaves the rest to the user.
 */
export function formatDate(field: DateField, date: YearMonth): Value | null {
	const { year, month } = date;
	if (field.part === 'year') return pick(field, [String(year)]);
	if (field.part === 'month') return month ? pick(field, monthSpellings(month)) : null;
	if (field.type === 'month') return month ? same(`${year}-${pad(month)}`) : null;
	// A date input needs a day the CV does not have: the first of the month, shown in review.
	if (field.type === 'date') return month ? same(`${year}-${pad(month)}-01`) : null;
	if (field.options) return pick(field, [String(year)]);
	const hint = field.placeholder.toLowerCase();
	if (!month) return same(String(year));
	if (/yyyy\s*-\s*mm/.test(hint)) return same(`${year}-${pad(month)}`);
	if (/mm\s*-\s*yyyy/.test(hint)) return same(`${pad(month)}-${year}`);
	if (/mm\s*\/\s*yy(?!yy)/.test(hint)) return same(`${pad(month)}/${String(year).slice(2)}`);
	if (/month|mmm/.test(hint)) return same(`${MONTH_NAMES[month - 1]} ${year}`);
	return same(`${pad(month)}/${year}`);
}

function same(text: string): Value {
	return { value: text, display: text };
}

/** For a list, the matching option; for a text field, the first spelling. */
export function pick(field: { options: Option[] | null }, spellings: string[]): Value | null {
	const first = spellings.find((s) => s.trim() !== '');
	if (first === undefined) return null;
	if (!field.options) return same(first);
	const option = matchOption(field.options, spellings);
	return option ? { value: option.value, display: option.text } : null;
}

/**
 * Text cut to a field's length limit, dropping whole lines from the end so a description keeps
 * complete bullets; a single line too long is cut at a word.
 */
export function fitLines(text: string, max: number | null): { text: string; shortened: boolean } {
	if (!max || text.length <= max) return { text, shortened: false };
	const lines = text.split('\n');
	while (lines.length > 1 && lines.join('\n').length > max) lines.pop();
	let fitted = lines.join('\n').trimEnd();
	if (fitted.length > max) {
		const cut = fitted.slice(0, max);
		const space = cut.lastIndexOf(' ');
		fitted = (space > max / 2 ? cut.slice(0, space) : cut).trimEnd();
	}
	return { text: fitted, shortened: true };
}

/** What lists call each level of degree, most specific first. */
export const DEGREE_LEVELS: Record<string, string[]> = {
	doctorate: ['Doctorate', 'Doctor of Philosophy', 'PhD', 'Ph.D.', 'Doctoral', 'Doctor'],
	master: ["Master's Degree", "Master's", 'Masters', 'Master', 'MSc', 'MA', 'Postgraduate'],
	bachelor: [
		"Bachelor's Degree",
		"Bachelor's",
		'Bachelors',
		'Bachelor',
		'BSc',
		'BA',
		'Undergraduate'
	],
	associate: ["Associate's Degree", "Associate's", 'Associate'],
	high_school: ['High School', 'High School Diploma', 'Secondary School', 'Secondary', 'GED']
};
