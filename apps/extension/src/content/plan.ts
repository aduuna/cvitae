import { isRepeated } from './classify.ts';
import type {
	ApplicationData,
	Assignment,
	Education,
	FieldInfo,
	FillPlan,
	PageScan,
	Role
} from './types.ts';
import { DEGREE_LEVELS, fitLines, formatDate, pick, type Value } from './values.ts';

interface Planned extends Value {
	shortened?: boolean;
}

function text(field: FieldInfo, value: string): Planned | null {
	if (!value.trim()) return null;
	if (field.options) return pick(field, [value]);
	const fitted = fitLines(value, field.maxLength);
	return { value: fitted.text, display: fitted.text, shortened: fitted.shortened };
}

function roleValue(field: FieldInfo, role: Role): Planned | null {
	switch (field.kind) {
		case 'experience.company':
			return text(field, role.company);
		case 'experience.title':
			return text(field, role.title);
		case 'experience.location':
			return text(field, role.location);
		case 'experience.description':
			return text(field, role.description);
		case 'experience.start':
			return role.start ? formatDate(field, role.start) : null;
		case 'experience.end':
			// A current role has no end date: the form's "current" box says so instead.
			return !role.current && role.end ? formatDate(field, role.end) : null;
		case 'experience.current':
			return role.current ? { value: 'true', display: 'Yes' } : { value: 'false', display: 'No' };
		default:
			return null;
	}
}

function educationValue(field: FieldInfo, school: Education): Planned | null {
	switch (field.kind) {
		case 'education.school':
			return text(field, school.institution);
		case 'education.degree':
			return field.options
				? pick(field, [school.degree, ...(DEGREE_LEVELS[school.level] ?? [])])
				: text(field, school.degree);
		case 'education.field':
			return text(field, school.field);
		case 'education.start':
			return school.start ? formatDate(field, school.start) : null;
		case 'education.end':
			return school.end ? formatDate(field, school.end) : null;
		default:
			return null;
	}
}

/** The value a field gets from the data, or null when the data has none for it. */
export function valueFor(field: FieldInfo, data: ApplicationData): Planned | null {
	const { name, location, links } = data;
	switch (field.kind) {
		case null:
			return null;
		case 'name.full':
			return text(field, name.full);
		case 'name.first':
			return text(field, name.first);
		case 'name.middle':
			return text(field, name.middle);
		case 'name.last':
			return text(field, name.last);
		case 'email':
			return text(field, data.email);
		case 'phone':
			return text(field, data.phone);
		case 'location.full':
			return text(field, location.full);
		case 'location.city':
			return text(field, location.city);
		case 'location.region':
			return location.region ? pick(field, location.region_names) : null;
		case 'location.country':
			return location.country ? pick(field, location.country_names) : null;
		case 'link.linkedin':
			return text(field, links.linkedin);
		case 'link.github':
			return text(field, links.github);
		case 'link.gitlab':
			return text(field, links.gitlab);
		case 'link.twitter':
			return text(field, links.twitter);
		case 'link.stackoverflow':
			return text(field, links.stackoverflow);
		case 'link.website':
			return text(field, links.website);
		case 'headline':
			return text(field, data.headline);
		case 'summary':
			return text(field, data.summary);
		case 'current.company':
			return text(field, data.current_company);
		case 'current.title':
			return text(field, data.current_title);
		case 'skills':
			return text(field, data.skills.join(', '));
	}
	if (field.kind.startsWith('experience.')) {
		const role = data.experience[field.group];
		return role ? roleValue(field, role) : null;
	}
	const school = data.education[field.group];
	return school ? educationValue(field, school) : null;
}

function slots(fields: FieldInfo[], prefix: string): number {
	const groups = new Set(fields.filter((f) => f.kind?.startsWith(prefix)).map((f) => f.group));
	return groups.size;
}

/**
 * What to write where. Fields that have a value already are planned but left unticked, so the
 * user can choose to replace them; a checkbox already in the right state is left out.
 */
export function planFill(fields: FieldInfo[], data: ApplicationData): FillPlan {
	const assignments: Assignment[] = [];
	for (const field of fields) {
		if (!field.kind) continue;
		const planned = valueFor(field, data);
		if (!planned) continue;
		if (field.type === 'checkbox' && (planned.value === 'true') === field.filled) continue;
		assignments.push({
			fieldId: field.id,
			kind: field.kind,
			group: field.group,
			label: field.label,
			value: planned.value,
			display: planned.display,
			include: !field.filled,
			filled: field.filled,
			needsChoice: field.needsChoice,
			shortened: planned.shortened ?? false
		});
	}
	return {
		assignments,
		experience: { slots: slots(fields, 'experience.'), total: data.experience.length },
		education: { slots: slots(fields, 'education.'), total: data.education.length }
	};
}

/**
 * An application form, or one step of it: two contact fields, three fields of roles or schools
 * (Workday asks for experience on a step of its own), or a CV upload next to a couple of fields.
 */
export function looksLikeApplication(page: PageScan): boolean {
	const kinds = new Set(page.fields.map((field) => field.kind));
	const contact = (['email', 'name.full', 'name.first', 'phone'] as const).filter((kind) =>
		kinds.has(kind)
	);
	const history = page.fields.filter((field) => field.kind && isRepeated(field.kind));
	return (
		contact.length >= 2 || history.length >= 3 || (page.files.length > 0 && page.fields.length >= 2)
	);
}
