import type { ApplicationData, YearMonth } from '../content/types.ts';
import { MONTH_NAMES } from '../content/values.ts';

export interface DetailItem {
	label: string;
	value: string;
}

export interface DetailGroup {
	title: string;
	items: DetailItem[];
}

function date(value: YearMonth | null): string {
	if (!value) return '';
	return value.month
		? `${MONTH_NAMES[value.month - 1]?.slice(0, 3)} ${value.year}`
		: `${value.year}`;
}

export function dates(start: YearMonth | null, end: YearMonth | null, current = false): string {
	const from = date(start);
	const to = current ? 'present' : date(end);
	return from && to ? `${from} to ${to}` : from || to;
}

function items(list: [string, string][]): DetailItem[] {
	return list.filter(([, value]) => value.trim()).map(([label, value]) => ({ label, value }));
}

/** The data as groups of labelled values, to copy into fields the extension cannot fill. */
export function detailGroups(data: ApplicationData): DetailGroup[] {
	const { links } = data;
	const groups: DetailGroup[] = [
		{
			title: 'Your details',
			items: items([
				['Name', data.name.full],
				['Email', data.email],
				['Phone', data.phone],
				['Location', data.location.full],
				['Headline', data.headline],
				['Summary', data.summary],
				['Skills', data.skills.join(', ')]
			])
		},
		{
			title: 'Links',
			items: items([
				['LinkedIn', links.linkedin],
				['GitHub', links.github],
				['GitLab', links.gitlab],
				['Twitter', links.twitter],
				['Stack Overflow', links.stackoverflow],
				['Website', links.website],
				...links.other.map((url): [string, string] => ['Link', url])
			])
		},
		...data.experience.map((role) => ({
			title: [role.title, role.company].filter(Boolean).join(' at '),
			items: items([
				['Company', role.company],
				['Title', role.title],
				['Location', role.location],
				['Dates', dates(role.start, role.end, role.current)],
				['Description', role.description]
			])
		})),
		...data.education.map((school) => ({
			title: school.institution,
			items: items([
				['School', school.institution],
				['Degree', school.degree],
				['Field of study', school.field],
				['Dates', dates(school.start, school.end)]
			])
		}))
	];
	return groups.filter((group) => group.items.length > 0);
}
