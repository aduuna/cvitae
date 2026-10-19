import { planFill } from '../content/plan.ts';
import type { ApplicationData, Assignment, FieldKind } from '../content/types.ts';
import type { FrameScan } from '../lib/page.ts';

/** A planned fill as the review shows it. */
export interface Row extends Assignment {
	frameId: number;
	/** A text field: the user can change the value before it is written. */
	editable: boolean;
	/** Long text (a description or summary) gets a text area. */
	long: boolean;
}

export interface Review {
	rows: Row[];
	notes: string[];
}

const LONG: readonly FieldKind[] = ['experience.description', 'summary'];

export function plural(count: number, one: string, many = `${one}s`): string {
	return `${count} ${count === 1 ? one : many}`;
}

/** The plan for every frame, and what the user should know about it. */
export function review(frames: FrameScan[], data: ApplicationData, source: string): Review {
	const rows: Row[] = [];
	const experience = { slots: 0, total: data.experience.length };
	const education = { slots: 0, total: data.education.length };
	for (const { frameId, scan } of frames) {
		const plan = planFill(scan.fields, data);
		const byId = new Map(scan.fields.map((field) => [field.id, field]));
		for (const assignment of plan.assignments) {
			const field = byId.get(assignment.fieldId);
			rows.push({
				...assignment,
				frameId,
				editable: field?.tag !== 'select' && field?.type !== 'checkbox',
				long: LONG.includes(assignment.kind)
			});
		}
		experience.slots += plan.experience.slots;
		education.slots += plan.education.slots;
	}

	const notes: string[] = [];
	if (experience.slots > 0 && experience.slots < experience.total) {
		notes.push(
			`The form has room for ${experience.slots} of your ${plural(experience.total, 'role')}. Add another role in the form, then fill again.`
		);
	}
	if (education.slots > 0 && education.slots < education.total) {
		notes.push(
			`The form has room for ${education.slots} of your ${plural(education.total, 'school')}. Add another in the form, then fill again.`
		);
	}
	const filled = rows.filter((row) => row.filled).length;
	if (filled) {
		notes.push(
			`${plural(filled, 'field has', 'fields have')} a value already and ${filled === 1 ? 'is' : 'are'} left as ${filled === 1 ? 'it is' : 'they are'}. Tick to replace.`
		);
	}
	const choices = rows.filter((row) => row.needsChoice).length;
	if (choices) {
		notes.push(
			`${plural(choices, 'field offers', 'fields offer')} a list as you type. Pick the right entry after filling.`
		);
	}
	const shortened = rows.filter((row) => row.shortened).length;
	if (shortened) {
		notes.push(`${plural(shortened, 'text was', 'texts were')} shortened to fit the field.`);
	}
	if (data.placeholders) {
		notes.push(
			`Your ${source} has ${plural(data.placeholders, 'placeholder')} in square brackets. Replace ${data.placeholders === 1 ? 'it' : 'them'} with real details before you submit.`
		);
	}
	return { rows, notes };
}

/** The ticked rows, per frame, as the content script takes them. */
export function byFrame(rows: Row[]): [number, { fieldId: string; value: string }[]][] {
	const frames = new Map<number, { fieldId: string; value: string }[]>();
	for (const row of rows.filter((r) => r.include)) {
		frames.set(row.frameId, [
			...(frames.get(row.frameId) ?? []),
			{ fieldId: row.fieldId, value: row.value }
		]);
	}
	return [...frames];
}

/** Which part of the profile a row comes from, for the review's headings. */
export function section(row: Pick<Row, 'kind' | 'group'>, data: ApplicationData): string {
	if (row.kind.startsWith('experience.')) {
		const company = data.experience[row.group]?.company;
		return `Role ${row.group + 1}${company ? `: ${company}` : ''}`;
	}
	if (row.kind.startsWith('education.')) {
		const school = data.education[row.group]?.institution;
		return `School ${row.group + 1}${school ? `: ${school}` : ''}`;
	}
	if (row.kind.startsWith('link.')) return 'Links';
	return 'Your details';
}

/** Rows grouped under their section, in the order the sections first appear. */
export function grouped(rows: Row[], data: ApplicationData): { title: string; rows: Row[] }[] {
	const groups = new Map<string, Row[]>();
	for (const row of rows) {
		const title = section(row, data);
		groups.set(title, [...(groups.get(title) ?? []), row]);
	}
	return [...groups].map(([title, list]) => ({ title, rows: list }));
}
