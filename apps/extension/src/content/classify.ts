import type { DatePart, FieldInfo, FieldKind } from './types.ts';

/** A field as read from the page, before it is classified and given an id. */
export type Described = Omit<FieldInfo, 'id' | 'kind' | 'part' | 'group'>;
export interface Classified {
	kind: FieldKind;
	part: DatePart | null;
}

/** Lower case words: "job_application[firstName]" reads "job application first name". */
export function words(text: string): string {
	return text
		.replace(/([a-z])([A-Z])/g, '$1 $2')
		.replace(/[\u2018\u2019]/g, "'")
		.normalize('NFKD')
		.replace(/[\u0300-\u036f]/g, '')
		.toLowerCase()
		.replace(/[^a-z0-9@+#&']+/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

/** Inputs that never take profile data. Radios are left to the user: they are always questions. */
const SKIPPED_TYPES = new Set([
	'hidden',
	'submit',
	'button',
	'reset',
	'image',
	'file',
	'password',
	'search',
	'radio',
	'range',
	'color'
]);

/**
 * Questions the profile does not answer and the extension must never guess: equal opportunity
 * monitoring, eligibility, pay, other people's details, and free-text answers the user writes.
 */
const NEVER =
	/\b(gender|sex|sexual|race|racial|ethnic\w*|hispanic|latin[oax]|veteran|disabilit\w*|disabled|pronouns?|religio\w*|birth|dob|age|nationality|citizen\w*|visa|sponsor\w*|authori[sz]\w*|eligib\w*|right to work|clearance|salary|compensation|pay|wage|rate|notice|relocat\w*|referr\w*|referral|reference|refer|hear about|how did you|source|recruiter|manager|emergency|cover letter|motivation|why do you|why are you|captcha|password|coupon|promo|years of experience|how many years|signature|consent|agree|acknowledge|terms|privacy|gdpr)\b/;

const SECTION_EXPERIENCE =
	/\b(work experience|experience|employment|work history|employment history|employer|professional history|positions? held|career history)\b/;
const SECTION_EDUCATION =
	/\b(education|educational|school|universit\w*|college|academic|qualifications?|degrees?)\b/;

type Section = 'experience' | 'education' | null;

function sectionOf(context: string, hints: string): Section {
	// The heading closest to the field wins; hints catch automation ids like "workExperience-2".
	const experience =
		SECTION_EXPERIENCE.test(context) || /\bwork experience\b|\bemployment\b/.test(hints);
	const education = SECTION_EDUCATION.test(context) || /\beducation\b/.test(hints);
	if (experience && !education) return 'experience';
	if (education && !experience) return 'education';
	if (experience && education) {
		// Both, as in "Education and experience": the later word in the heading is more specific.
		return context.lastIndexOf('educat') > context.lastIndexOf('experien')
			? 'education'
			: 'experience';
	}
	return null;
}

const AUTOCOMPLETE: Record<string, FieldKind> = {
	name: 'name.full',
	'given-name': 'name.first',
	'additional-name': 'name.middle',
	'family-name': 'name.last',
	email: 'email',
	tel: 'phone',
	'tel-national': 'phone',
	'address-level2': 'location.city',
	'address-level1': 'location.region',
	country: 'location.country',
	'country-name': 'location.country',
	organization: 'current.company',
	'organization-title': 'current.title',
	url: 'link.website'
};

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

/** Whether a field takes a month or a year when a date is split in two. */
export function datePart(field: Described, text: string): DatePart | null {
	const month = /\bmonth\b|\bmm\b/.test(text);
	const year = /\byear\b|\byyyy\b|\byy\b/.test(text);
	if (month && !year) return 'month';
	if (year && !month) return 'year';
	if (field.options) {
		const texts = field.options.map((option) => words(option.text)).filter(Boolean);
		if (
			texts.length &&
			texts.every((t) => /^\d{4}$/.test(t) || !/\d/.test(t)) &&
			texts.some((t) => /^\d{4}$/.test(t))
		) {
			return 'year';
		}
		if (texts.filter((t) => MONTHS.some((m) => t.startsWith(m))).length >= 12) return 'month';
	}
	const placeholder = field.placeholder.trim().toLowerCase();
	if (field.maxLength === 4 || /^y{4}$/.test(placeholder)) return 'year';
	if (field.maxLength === 2 || /^m{2}$/.test(placeholder)) return 'month';
	return null;
}

const DATEISH = /\b(date|month|year|mm|yyyy|from|to|start|end|since|until|graduat\w*|completion)\b/;
const START = /\b(start|from|begin\w*|since|joined)\b/;
const END = /\b(end|to|until|finish\w*|left|leaving|graduat\w*|completion|completed)\b/;

function dateKind(
	field: Described,
	label: string,
	all: string,
	section: Section
): Classified | null {
	if (field.tag === 'textarea') return null;
	const typed = field.type === 'date' || field.type === 'month';
	if (!typed && !DATEISH.test(all)) return null;
	const graduation = /\bgraduat\w*|year of completion|completion date\b/.test(all);
	const target = graduation ? 'education' : section;
	if (target === null) return null;
	// The label decides first: hints of an ancestor may name both ends of a range.
	const end = END.test(label) || (!START.test(label) && END.test(all));
	const start = !end && (START.test(label) || START.test(all));
	if (!start && !end) return null;
	return {
		kind: `${target}.${end ? 'end' : 'start'}`,
		part: typed ? null : datePart(field, all)
	};
}

const DESCRIPTION =
	/\b(description|describe|responsibilit\w*|duties|achievements?|summary|details|accomplishments?)\b/;

function experienceKind(
	field: Described,
	label: string,
	hints: string[],
	all: string
): FieldKind | null {
	if (field.type === 'checkbox') {
		return /\b(current\w*|present|still|i work here)\b/.test(all) ? 'experience.current' : null;
	}
	// The label decides; attributes count only when they name the field outright. Generic names
	// like Greenhouse's "job_application[...]" must not make every field a job title.
	const named = (inLabel: RegExp, inHint: RegExp) =>
		inLabel.test(label) ||
		hints.some((hint) => inHint.test(hint) && !/\bjob application\b/.test(hint));
	if (field.tag === 'textarea') {
		return named(DESCRIPTION, /\bdescription\b/) ? 'experience.description' : null;
	}
	if (
		named(
			/\b(company|employer|organi[sz]ation|business)\b/,
			/\b(company|employer|organi[sz]ation)\b|^org$/
		)
	) {
		return 'experience.company';
	}
	if (named(/\b(title|position|role)\b/, /\bjob title\b|^title$|\bposition\b|\brole\b/)) {
		return 'experience.title';
	}
	if (named(/\b(location|city|where)\b/, /\blocation\b/)) return 'experience.location';
	if (named(DESCRIPTION, /\bdescription\b/)) return 'experience.description';
	return null;
}

function educationKind(field: Described, all: string): FieldKind | null {
	if (field.type === 'checkbox') return null;
	if (/\b(gpa|cgpa|grade|grades|honou?rs|class of degree|score)\b/.test(all)) return null;
	if (
		/\b(field of study|major|discipline|subject|area of study|course|programme?|speciali[sz]\w*|concentration)\b/.test(
			all
		)
	) {
		return 'education.field';
	}
	if (/\b(degree|qualification|level of (education|study)|diploma|award)\b/.test(all)) {
		return 'education.degree';
	}
	if (/\b(school|universit\w*|college|institution|institute|academy|name)\b/.test(all)) {
		return 'education.school';
	}
	return null;
}

const NOT_A_PERSON =
	/\b(company|employer|school|universit\w*|institution|organi[sz]ation|preferred|nick ?name|also known|known as|maiden|previous|former)\b/;

function basicsKind(
	field: Described,
	label: string,
	hints: string[],
	all: string
): FieldKind | null {
	const hinted = (re: RegExp) => re.test(label) || hints.some((hint) => re.test(hint));
	if (field.type === 'checkbox') return null;
	if (field.type === 'email' || hinted(/\be ?mail\b/)) return 'email';
	if (field.type === 'tel' || hinted(/\b(phone|mobile|telephone|cell|tel)\b/)) {
		return /\b(type|extension|ext|code|device|dial)\b/.test(all) ? null : 'phone';
	}
	if (hinted(/\blinked ?in\b/)) return 'link.linkedin';
	if (hinted(/\bgit ?hub\b/)) return 'link.github';
	if (hinted(/\bgit ?lab\b/)) return 'link.gitlab';
	if (hinted(/\btwitter\b|\bx (profile|handle|url|account)\b|\bx com\b/)) return 'link.twitter';
	if (hinted(/\bstack ?overflow\b/)) return 'link.stackoverflow';
	if (!NOT_A_PERSON.test(all)) {
		if (hinted(/\b(first|given|fore) ?name\b|\bfname\b|^first$/)) return 'name.first';
		if (hinted(/\b(last|family|sur) ?name\b|\blname\b|\bsurname\b|^last$/)) return 'name.last';
		if (hinted(/\bmiddle ?(name|initials?)?\b/)) return 'name.middle';
		if (
			/^(your |full |legal |candidate |applicant )?name$|\bfull ?name\b|\blegal name\b/.test(
				label
			) ||
			hints.some((hint) =>
				/^name$|\bfull ?name\b|\b(candidate|applicant) name\b|systemfield name$/.test(hint)
			)
		) {
			return 'name.full';
		}
	}
	if (
		hinted(
			/\b(web ?site|portfolio|personal (site|url|page|link)|blog|home ?page|other (link|url|profile|web ?site))\b/
		) ||
		field.type === 'url'
	) {
		return 'link.website';
	}
	// Street addresses and postal codes match nothing below: the profile has none.
	if (hinted(/\bcountry\b|\bnation\b/))
		return /\b(code|phone|dial)\b/.test(all) ? null : 'location.country';
	if (hinted(/\blocation\b|\bwhere (are you|do you) (based|live|located)\b|\bbased in\b/))
		return 'location.full';
	if (hinted(/\b(city|town)\b/)) return 'location.city';
	if (hinted(/\b(state|province|region|county)\b/)) return 'location.region';
	if (
		hinted(
			/\b(current|present|most recent|latest) (company|employer|organi[sz]ation)\b|\bcompany\b|\bemployer\b|^org$/
		)
	) {
		return 'current.company';
	}
	if (
		hinted(/\b(current|present|most recent|latest) (job )?(title|role|position)\b|\bjob title\b/)
	) {
		return 'current.title';
	}
	if (hinted(/\bheadline\b|\bprofessional title\b|\btagline\b/)) return 'headline';
	if (/\b(skills?|technologies|tech stack|competenc\w*|expertise)\b/.test(all)) return 'skills';
	if (
		field.tag === 'textarea' &&
		/\b(summary|about (you|yourself|me)|bio|biography|introduce yourself|tell us about yourself|professional profile)\b/.test(
			all
		)
	) {
		return 'summary';
	}
	return null;
}

/** What a field asks for, or null when the profile does not answer it. */
export function classify(field: Described): Classified | null {
	if (field.tag === 'input' && SKIPPED_TYPES.has(field.type)) return null;
	const label = words(field.label);
	const hints = field.hints.map(words).filter(Boolean);
	const context = words(field.context);
	const placeholder = words(field.placeholder);
	const all = [label, placeholder, ...hints].join(' ');
	if (NEVER.test(label) || NEVER.test(all)) return null;

	const section = sectionOf(context, hints.join(' '));
	const date = dateKind(field, label, all, section);
	if (date) return date;

	if (section === 'experience') {
		const kind = experienceKind(field, label, hints, all);
		if (kind) return { kind, part: null };
	}
	if (
		section === 'education' ||
		(section === null && /\b(school|universit\w*|degree|field of study|major)\b/.test(label))
	) {
		const kind = educationKind(field, all);
		if (kind) return { kind, part: null };
	}
	if (
		section === null &&
		field.type === 'checkbox' &&
		/\b(i (currently )?work here|current (job|role|position|employer))\b/.test(all)
	) {
		return { kind: 'experience.current', part: null };
	}

	const autocomplete =
		AUTOCOMPLETE[field.autocomplete.trim().toLowerCase().split(/\s+/).at(-1) ?? ''];
	if (autocomplete) {
		if (section === 'experience' && autocomplete === 'current.company')
			return { kind: 'experience.company', part: null };
		if (section === 'experience' && autocomplete === 'current.title')
			return { kind: 'experience.title', part: null };
		return { kind: autocomplete, part: null };
	}
	const kind = basicsKind(field, label, hints, all);
	return kind ? { kind, part: null } : null;
}

/** Kinds that repeat once per role or school. */
export function isRepeated(kind: FieldKind): boolean {
	return kind.startsWith('experience.') || kind.startsWith('education.');
}
