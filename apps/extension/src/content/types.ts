import type { Schemas } from '@web/api/client.ts';

/** What the api returns for filling forms (cvcore/application.py). */
export type ApplicationData = Schemas['ApplicationData'];
export type Role = Schemas['Role'];
export type Education = Schemas['Education'];
export type YearMonth = Schemas['YearMonth'];

/** What a form field asks for. Repeated sections (roles, schools) carry a group index. */
export type FieldKind =
	| 'name.full'
	| 'name.first'
	| 'name.middle'
	| 'name.last'
	| 'email'
	| 'phone'
	| 'location.full'
	| 'location.city'
	| 'location.region'
	| 'location.country'
	| 'link.linkedin'
	| 'link.github'
	| 'link.gitlab'
	| 'link.twitter'
	| 'link.stackoverflow'
	| 'link.website'
	| 'headline'
	| 'summary'
	| 'current.company'
	| 'current.title'
	| 'skills'
	| 'experience.company'
	| 'experience.title'
	| 'experience.location'
	| 'experience.start'
	| 'experience.end'
	| 'experience.current'
	| 'experience.description'
	| 'education.school'
	| 'education.degree'
	| 'education.field'
	| 'education.start'
	| 'education.end';

/** For dates split into two controls. */
export type DatePart = 'month' | 'year';

export interface Option {
	value: string;
	text: string;
}

/**
 * A form control as the content script sees it. Serializable: it travels from the page to the
 * side panel. It says whether the field has a value, never what the value is.
 */
export interface FieldInfo {
	/** Unique within one scan of one frame. */
	id: string;
	tag: 'input' | 'textarea' | 'select';
	/** The input's type; "textarea" and "select" for those. */
	type: string;
	/** The visible label, cleaned of required markers. */
	label: string;
	/** The heading of the section around the field, for example "Work experience". */
	context: string;
	/** name, id, autocomplete and automation attributes of the field and its close ancestors. */
	hints: string[];
	autocomplete: string;
	placeholder: string;
	maxLength: number | null;
	options: Option[] | null;
	filled: boolean;
	/** A combobox or autocomplete: typing offers choices the user has to pick from. */
	needsChoice: boolean;
	kind: FieldKind | null;
	part: DatePart | null;
	/** Which role or school, counted in page order; 0 outside repeated sections. */
	group: number;
}

/** A file input that takes a CV. */
export interface FileField {
	id: string;
	label: string;
	hasFile: boolean;
}

/**
 * An open question on the form: a free-text field the profile does not fill, which the user can
 * have drafted (docs/PRODUCT.md, 8, Answer questions). Like a field, it never carries its value.
 */
export interface QuestionInfo {
	id: string;
	/** The question as the form labels it. */
	label: string;
	/** Help text the form gives for it, such as "Please answer in 200 words or fewer". */
	help: string;
	/** A text area; false for a single-line field. */
	multiline: boolean;
	/** The field's own length limit. */
	maxLength: number | null;
	/** A word limit the label or help text states. */
	maxWords: number | null;
	/** The tighter of the field's length limit and one the label or help text states. */
	maxChars: number | null;
	filled: boolean;
}

export interface PageScan {
	url: string;
	title: string;
	fields: FieldInfo[];
	files: FileField[];
	questions: QuestionInfo[];
	/** A sentence on the page asking applicants not to use AI, when there is one. */
	aiPolicy: string | null;
}

/** One field to fill and the value it gets. */
export interface Assignment {
	fieldId: string;
	kind: FieldKind;
	group: number;
	label: string;
	/** What is written: text, an option's value, or "true"/"false" for a checkbox. */
	value: string;
	/** What the user reads in the review: the option's text for a list. */
	display: string;
	/** Filled unless the user unticks it. Off for fields that have a value already. */
	include: boolean;
	filled: boolean;
	needsChoice: boolean;
	/** The text was shortened to the field's length limit, whole lines at a time. */
	shortened: boolean;
}

export interface FillPlan {
	assignments: Assignment[];
	/** Roles and schools the form has room for, and how many the CV has. */
	experience: { slots: number; total: number };
	education: { slots: number; total: number };
}

/** A job ad read from the page, to save to Tailor. */
export interface JobDraft {
	title: string;
	company: string;
	url: string;
	description: string;
	/** Where the description came from: the page's job posting data is the most reliable. */
	from: 'posting' | 'selection' | 'page';
}

/** Fills that are undone separately: the profile's fields, and drafted answers. */
export type FillBatch = 'fields' | 'answers';

/** What the content script exposes to the extension's own scripts (scripting.executeScript). */
export interface ContentApi {
	scan(): PageScan;
	fill(assignments: Pick<Assignment, 'fieldId' | 'value'>[], batch?: FillBatch): number;
	undo(batch?: FillBatch): number;
	attach(fieldId: string, file: { name: string; type: string; base64: string }): boolean;
	job(): JobDraft | null;
}

declare global {
	/** The content script in this frame, shared by the extension's scripts in its isolated world. */
	var __cvitae: ContentApi | undefined;
	/** Set by the side panel before it injects the content script: the panel is open, no prompt. */
	var __cvitaeQuiet: boolean | undefined;
}
