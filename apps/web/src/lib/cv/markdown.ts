/**
 * CV content as Markdown, for the editor's Markdown mode (docs/PRODUCT.md, "Markdown format").
 *
 * `toMarkdown` writes the content; `fromMarkdown` reads it back, keeping the ids (and so the
 * `source_id` links) of everything the text still holds. For content the form can produce,
 * `fromMarkdown(toMarkdown(content), content)` returns `content` unchanged. Single-line fields are
 * trimmed and keep no line breaks, comma lists drop empty items, and an end date of "present" is
 * the same as none: none of that changes what the CV shows. An empty end date (which also shows as
 * present) is written as a bare `to`, so it stays empty rather than becoming none.
 */
import { newId } from './factory';
import type {
	Basics,
	Bullet,
	CertificationItem,
	CvContent,
	DateRange,
	EducationItem,
	Engagement,
	ExperienceItem,
	Link,
	ProjectItem,
	Section,
	SectionKind,
	SkillGroup
} from './types';

export interface MarkdownError {
	/** 1-based line number. */
	line: number;
	message: string;
}

export type MarkdownResult =
	{ ok: true; content: CvContent } | { ok: false; errors: MarkdownError[] };

const KINDS: readonly SectionKind[] = [
	'experience',
	'projects',
	'education',
	'skills',
	'certifications',
	'custom'
];

const DEFAULT_LABEL = 'Client';

// ---------------------------------------------------------------------------------------------
// Writing

export function toMarkdown(content: CvContent): string {
	const out: string[] = [];
	const { basics } = content;
	out.push(heading(1, basics.name));
	field(out, 'Headline', basics.headline);
	field(out, 'Email', basics.email);
	field(out, 'Phone', basics.phone);
	field(out, 'Location', basics.location);
	for (const link of basics.links) out.push(`Link: [${oneLine(link.label)}](${oneLine(link.url)})`);

	const summary = content.summary.trim();
	if (summary) out.push('', ...summary.split('\n').map(escapeTextLine));

	for (const section of content.sections) {
		out.push('', `${heading(2, section.title)} {${section.kind}}`);
		writeSection(out, section);
	}
	return out.join('\n') + '\n';
}

function writeSection(out: string[], section: Section): void {
	switch (section.kind) {
		case 'experience':
			for (const item of section.experience) {
				out.push('', heading(3, item.org));
				field(out, 'Role', item.role);
				field(out, 'Location', item.location);
				field(out, 'Dates', formatDates(item.dates));
				field(out, 'Stack', formatList(item.stack));
				writeBullets(out, item.bullets);
				for (const engagement of item.engagements) {
					out.push('', heading(4, engagement.name));
					if (engagement.label !== DEFAULT_LABEL) {
						out.push(`Label: ${oneLine(engagement.label)}`.trimEnd());
					}
					field(out, 'Location', engagement.location);
					field(out, 'Dates', engagement.dates ? formatDates(engagement.dates) : '');
					writeBullets(out, engagement.bullets);
				}
			}
			break;
		case 'projects':
			for (const item of section.projects) {
				out.push('', heading(3, item.name));
				field(out, 'URL', item.url ?? '');
				field(out, 'Status', item.status);
				field(out, 'Year', item.year);
				writeBullets(out, item.bullets);
			}
			break;
		case 'education':
			for (const item of section.education) {
				out.push('', heading(3, item.institution));
				field(out, 'Degree', item.degree);
				field(out, 'Location', item.location);
				field(out, 'Dates', formatDates(item.dates));
			}
			break;
		case 'certifications':
			for (const item of section.certifications) {
				out.push('', heading(3, item.name));
				field(out, 'Issuer', item.issuer);
				field(out, 'Date', item.date);
			}
			break;
		case 'skills':
			if (section.skills.length) out.push('');
			for (const group of section.skills) {
				out.push(
					`- ${escapeChars(oneLine(group.label), ':')}: ${formatList(group.items)}`.trimEnd()
				);
			}
			break;
		case 'custom':
			writeBullets(out, section.custom);
			break;
	}
}

function writeBullets(out: string[], bullets: Bullet[]): void {
	if (!bullets.length) return;
	out.push('');
	for (const bullet of bullets) {
		const [first = '', ...rest] = bullet.text.trim().split('\n');
		out.push(first ? `- ${first}` : '-', ...rest.map((line) => `  ${line}`));
	}
}

function heading(level: number, text: string): string {
	return `${'#'.repeat(level)} ${oneLine(text)}`.trimEnd();
}

function field(out: string[], key: string, value: string): void {
	const text = oneLine(value);
	if (text) out.push(`${key}: ${text}`);
}

/** A single-line field as it is written: no line breaks, no outer spaces. */
function oneLine(text: string): string {
	return text.replace(/\s*\n\s*/g, ' ').trim();
}

function isPresent(end: string): boolean {
	return /^present$/i.test(end.trim());
}

function formatDates(dates: DateRange): string {
	const start = oneLine(dates.start);
	if (dates.end === null) return start ? `${start} to present` : '';
	const end = oneLine(dates.end);
	if (isPresent(end)) return start ? `${start} to present` : 'to present';
	if (start === end && end) return start;
	if (!end) return start ? `${start} to` : 'to';
	return start ? `${start} to ${end}` : `to ${end}`;
}

function formatList(items: string[]): string {
	return items
		.map((item) => escapeChars(oneLine(item), ','))
		.filter(Boolean)
		.join(', ');
}

/**
 * Backslash-escape `chars`. A backslash is escaped only where it could be read as an escape: before
 * one of `chars`, before another backslash, or at the end.
 */
function escapeChars(text: string, chars: string): string {
	let out = '';
	for (let i = 0; i < text.length; i++) {
		const char = text[i] as string;
		const next = text[i + 1];
		if (chars.includes(char)) out += `\\${char}`;
		else if (char === '\\' && (next === undefined || next === '\\' || chars.includes(next)))
			out += '\\\\';
		else out += char;
	}
	return out;
}

/** Summary lines must not read as headings: a leading `#` (or an escape) gets a backslash. */
function escapeTextLine(line: string): string {
	return /^(#|\\#|\\\\)/.test(line) ? `\\${line}` : line;
}

// ---------------------------------------------------------------------------------------------
// Reading

const HEADING = /^(#{1,6})(?:[ \t]+(.*?))?[ \t]*$/;
const BULLET = /^[-*](?:[ \t]+(.*))?$/;
const FIELD = /^([A-Za-z][A-Za-z ]{0,19}?)[ \t]*:[ \t]*(.*?)[ \t]*$/;
const SECTION_KIND = new RegExp(`^(.*?)[ \\t]*\\{(${KINDS.join('|')})\\}$`);

const FIELDS = {
	basics: ['headline', 'email', 'phone', 'location', 'link'],
	experience: ['role', 'location', 'dates', 'stack'],
	engagement: ['label', 'location', 'dates'],
	projects: ['url', 'status', 'year'],
	education: ['degree', 'location', 'dates'],
	certifications: ['issuer', 'date']
} as const;

const FIELD_NAMES: Record<string, string> = {
	headline: 'Headline',
	email: 'Email',
	phone: 'Phone',
	location: 'Location',
	link: 'Link',
	role: 'Role',
	dates: 'Dates',
	stack: 'Stack',
	label: 'Label',
	url: 'URL',
	status: 'Status',
	year: 'Year',
	degree: 'Degree',
	issuer: 'Issuer',
	date: 'Date'
};

type Entry = ExperienceItem | Engagement | ProjectItem | EducationItem | CertificationItem;

interface EntryState {
	kind: keyof typeof FIELDS;
	entry: Entry;
	seen: Set<string>;
	/** Bullets have started, so fields may no longer follow. */
	bullets: boolean;
}

/**
 * Read Markdown back into content. `previous` is the content the text was written from (or the
 * last valid parse); entries and bullets that are still there keep its ids.
 */
export function fromMarkdown(text: string, previous: CvContent): MarkdownResult {
	const lines = text.replace(/\r\n?/g, '\n').split('\n');
	const errors: MarkdownError[] = [];
	const fail = (index: number, message: string) => errors.push({ line: index + 1, message });

	let i = 0;
	while (i < lines.length && !lines[i]?.trim()) i++;
	const first = HEADING.exec(lines[i] ?? '');
	if (!first || first[1] !== '#') {
		fail(
			Math.min(i, lines.length - 1),
			'Start with the name as a # heading, like "# Ama Owusu-Mensah".'
		);
		return { ok: false, errors };
	}

	const basics: Basics = {
		name: first[2] ?? '',
		headline: '',
		email: '',
		phone: '',
		location: '',
		links: []
	};
	i++;
	const seenBasics = new Set<string>();
	for (; i < lines.length; i++) {
		const match = FIELD.exec(lines[i] as string);
		const key = match?.[1]?.toLowerCase() ?? '';
		if (!match || !(FIELDS.basics as readonly string[]).includes(key)) break;
		const value = match[2] ?? '';
		if (key === 'link') {
			const link = parseLink(value);
			if (typeof link === 'string') fail(i, link);
			else basics.links.push(link);
		} else if (seenBasics.has(key)) {
			fail(i, `${FIELD_NAMES[key]} is already set above.`);
		} else {
			seenBasics.add(key);
			basics[key as 'headline' | 'email' | 'phone' | 'location'] = value;
		}
	}

	const summary: string[] = [];
	for (; i < lines.length; i++) {
		const line = lines[i] as string;
		if (HEADING.test(line)) break;
		summary.push(/^\\(#|\\)/.test(line) ? line.slice(1) : line);
	}

	const sections: Section[] = [];
	let section: Section | null = null;
	let item: EntryState | null = null;
	let engagement: EntryState | null = null;
	let bullet: Bullet | null = null;

	for (; i < lines.length; i++) {
		const line = lines[i] as string;
		if (bullet && /^( {2}|\t)/.test(line)) {
			bullet.text += '\n' + line.replace(/^( {2}|\t)/, '');
			continue;
		}
		bullet = null;
		const trimmed = line.trim();
		if (!trimmed) continue;

		const head = HEADING.exec(trimmed);
		if (head) {
			const level = (head[1] as string).length;
			const title = head[2] ?? '';
			if (level === 1) {
				fail(i, 'Use # only once, for the name. Start sections with ##.');
			} else if (level === 2) {
				const kind = SECTION_KIND.exec(title);
				section = emptySection(
					kind ? (kind[2] as SectionKind) : 'custom',
					kind ? (kind[1] as string) : title
				);
				sections.push(section);
				item = engagement = null;
			} else if (!section) {
				fail(i, 'Start a section with a ## heading first.');
			} else if (level === 3) {
				engagement = null;
				item = startItem(section, title);
				if (!item) fail(i, noEntriesMessage(section.kind));
			} else if (level === 4 && section.kind === 'experience' && item) {
				const engagementEntry = newEngagementEntry(title);
				(item.entry as ExperienceItem).engagements.push(engagementEntry);
				engagement = {
					kind: 'engagement',
					entry: engagementEntry,
					seen: new Set(),
					bullets: false
				};
			} else {
				fail(i, 'Use #### only for a client inside an experience entry.');
			}
			continue;
		}

		// Lines under a misplaced heading: the heading is already reported.
		if (!section) continue;

		const listItem = BULLET.exec(line.trimStart());
		if (listItem) {
			const body = listItem[1] ?? '';
			if (section.kind === 'skills') {
				const group = parseSkill(body);
				if (typeof group === 'string') fail(i, group);
				else section.skills.push(group);
			} else if (section.kind === 'custom') {
				bullet = { id: '', text: body, source_id: null };
				section.custom.push(bullet);
			} else {
				const target = engagement ?? item;
				if (!target) {
					fail(i, 'Add a ### heading for the entry before its bullets.');
				} else if (target.kind === 'education' || target.kind === 'certifications') {
					fail(
						i,
						`${target.kind === 'education' ? 'Education entries' : 'Certifications'} have no bullets.`
					);
				} else {
					target.bullets = true;
					bullet = { id: '', text: body, source_id: null };
					(target.entry as ExperienceItem | Engagement | ProjectItem).bullets.push(bullet);
				}
			}
			continue;
		}

		const fieldMatch = FIELD.exec(trimmed);
		const target = engagement ?? item;
		if (fieldMatch && target && section.kind !== 'skills' && section.kind !== 'custom') {
			const key = (fieldMatch[1] as string).toLowerCase();
			const allowed: readonly string[] = FIELDS[target.kind];
			if (target.bullets) {
				fail(i, 'Put fields right under the heading, before the bullets.');
			} else if (!allowed.includes(key)) {
				fail(
					i,
					`Unknown field "${fieldMatch[1]}". Use ${allowed.map((k) => FIELD_NAMES[k]).join(', ')}.`
				);
			} else if (target.seen.has(key)) {
				fail(i, `${FIELD_NAMES[key]} is already set for this entry.`);
			} else {
				target.seen.add(key);
				const problem = setField(target, key, fieldMatch[2] ?? '');
				if (problem) fail(i, problem);
			}
			continue;
		}

		if (section.kind === 'skills') fail(i, 'Write skills as "- Label: item, item".');
		else if (section.kind === 'custom') fail(i, 'Start each line of a custom section with "- ".');
		else if (!target) fail(i, 'Add a ### heading for the entry first.');
		else fail(i, 'Start bullets with "- ", and indent a continued bullet line by two spaces.');
	}

	if (errors.length) return { ok: false, errors };
	const content: CvContent = {
		schema_version: 1,
		basics,
		summary: summary.join('\n').trim(),
		sections
	};
	for (const each of content.sections) trimBullets(each);
	return { ok: true, content: keepIds(content, previous) };
}

function emptySection(kind: SectionKind, title: string): Section {
	return {
		id: '',
		kind,
		title,
		experience: [],
		projects: [],
		education: [],
		skills: [],
		certifications: [],
		custom: []
	};
}

function startItem(section: Section, title: string): EntryState | null {
	const state = (kind: EntryState['kind'], entry: Entry): EntryState => ({
		kind,
		entry,
		seen: new Set(),
		bullets: false
	});
	switch (section.kind) {
		case 'experience': {
			const entry: ExperienceItem = {
				id: '',
				org: title,
				role: '',
				location: '',
				dates: { start: '', end: null },
				stack: [],
				bullets: [],
				engagements: []
			};
			section.experience.push(entry);
			return state('experience', entry);
		}
		case 'projects': {
			const entry: ProjectItem = {
				id: '',
				name: title,
				url: null,
				status: '',
				year: '',
				bullets: []
			};
			section.projects.push(entry);
			return state('projects', entry);
		}
		case 'education': {
			const entry: EducationItem = {
				id: '',
				institution: title,
				degree: '',
				location: '',
				dates: { start: '', end: null }
			};
			section.education.push(entry);
			return state('education', entry);
		}
		case 'certifications': {
			const entry: CertificationItem = { id: '', name: title, issuer: '', date: '' };
			section.certifications.push(entry);
			return state('certifications', entry);
		}
		default:
			return null;
	}
}

function newEngagementEntry(name: string): Engagement {
	return { id: '', name, label: DEFAULT_LABEL, location: '', dates: null, bullets: [] };
}

function noEntriesMessage(kind: SectionKind): string {
	return kind === 'skills'
		? 'Skills have no ### entries. Write each group as "- Label: item, item".'
		: 'Custom sections hold bullets only. Remove the ### heading, or give the section a kind, like {projects}.';
}

/** Set one field of an entry; returns a message when the value is not valid. */
function setField(target: EntryState, key: string, value: string): string | null {
	const entry = target.entry as unknown as Record<string, unknown>;
	if (key === 'dates') {
		const dates = parseDates(value);
		entry.dates = target.kind === 'engagement' && !dates.start && dates.end === null ? null : dates;
	} else if (key === 'stack') {
		entry.stack = parseList(value);
	} else if (key === 'url') {
		if (value && !isWebUrl(value)) return 'Enter a full link, starting with https://.';
		entry.url = value || null;
	} else {
		entry[key] = value;
	}
	return null;
}

function parseDates(value: string): DateRange {
	const match = /^(?:(.*?)[ \t]+)?to(?:[ \t]+(.*))?$/i.exec(value);
	if (!match) return { start: value, end: value || null };
	const end = match[2] ?? '';
	return { start: match[1] ?? '', end: isPresent(end) ? null : end };
}

/** Comma-separated items; `\,` is a comma inside an item and `\\` a backslash. */
function parseList(value: string): string[] {
	const items: string[] = [];
	let current = '';
	for (let i = 0; i < value.length; i++) {
		const char = value[i] as string;
		const next = value[i + 1];
		if (char === '\\' && (next === ',' || next === '\\')) {
			current += next;
			i++;
		} else if (char === ',') {
			items.push(current);
			current = '';
		} else {
			current += char;
		}
	}
	items.push(current);
	return items.map((item) => item.trim()).filter(Boolean);
}

function parseSkill(body: string): SkillGroup | string {
	let label = '';
	for (let i = 0; i < body.length; i++) {
		const char = body[i] as string;
		const next = body[i + 1];
		if (char === '\\' && (next === ':' || next === '\\')) {
			label += next;
			i++;
		} else if (char === ':') {
			return { id: '', label: label.trim(), items: parseList(body.slice(i + 1)) };
		} else {
			label += char;
		}
	}
	return 'Write skills as "- Label: item, item".';
}

function parseLink(value: string): Link | string {
	const match = /^\[(.*)\]\((.*)\)$/.exec(value);
	if (!match) return 'Write links as "Link: [Label](https://...)".';
	const url = (match[2] as string).trim();
	if (!isWebUrl(url)) return 'Enter a full link, starting with https://.';
	return { label: (match[1] as string).trim(), url };
}

function isWebUrl(text: string): boolean {
	try {
		const url = new URL(text);
		return (url.protocol === 'https:' || url.protocol === 'http:') && url.hostname !== '';
	} catch {
		return false;
	}
}

function trimBullets(section: Section): void {
	const trim = (bullets: Bullet[]) => bullets.forEach((each) => (each.text = each.text.trim()));
	trim(section.custom);
	for (const item of section.experience) {
		trim(item.bullets);
		item.engagements.forEach((engagement) => trim(engagement.bullets));
	}
	section.projects.forEach((project) => trim(project.bullets));
}

// ---------------------------------------------------------------------------------------------
// Identity

/**
 * Give `next` the ids of the matching parts of `previous`: sections, entries and bullets that are
 * unchanged (matched by their text, in order), or edited in place (an unmatched one in the same
 * gap between unchanged ones). Everything else gets a new id.
 */
function keepIds(next: CvContent, previous: CvContent): CvContent {
	const sections = pair(previous.sections, next.sections, (s) => `${s.kind}\n${s.title}`, sameKind);
	next.sections.forEach((section, index) => {
		const old = sections[index];
		section.id = old?.id ?? newId();
		keepEntryIds(
			section.experience,
			old?.experience ?? [],
			(e) => `${e.org}\n${e.role}`,
			(e, o) => {
				keepBulletIds(e.bullets, o?.bullets ?? []);
				keepEntryIds(
					e.engagements,
					o?.engagements ?? [],
					(g) => `${g.name}\n${g.label}`,
					(g, og) => keepBulletIds(g.bullets, og?.bullets ?? [])
				);
			}
		);
		keepEntryIds(
			section.projects,
			old?.projects ?? [],
			(p) => p.name,
			(p, o) => keepBulletIds(p.bullets, o?.bullets ?? [])
		);
		keepEntryIds(section.education, old?.education ?? [], (e) => `${e.institution}\n${e.degree}`);
		keepEntryIds(section.skills, old?.skills ?? [], (g) => g.label);
		keepEntryIds(
			section.certifications,
			old?.certifications ?? [],
			(c) => `${c.name}\n${c.issuer}`
		);
		keepBulletIds(section.custom, old?.custom ?? []);
	});
	return next;
}

function sameKind(a: Section, b: Section): boolean {
	return a.kind === b.kind;
}

function keepEntryIds<T extends { id: string }>(
	next: T[],
	previous: T[],
	key: (item: T) => string,
	inner?: (item: T, old: T | undefined) => void
): void {
	const matches = pair(previous, next, key);
	next.forEach((item, index) => {
		const old = matches[index];
		item.id = old?.id ?? newId();
		inner?.(item, old);
	});
}

function keepBulletIds(next: Bullet[], previous: Bullet[]): void {
	const matches = pair(previous, next, (bullet) => bullet.text);
	next.forEach((bullet, index) => {
		const old = matches[index];
		bullet.id = old?.id ?? newId();
		bullet.source_id = old?.source_id ?? null;
	});
}

/**
 * For each item of `next`, the item of `previous` it continues, if any: first equal keys in order
 * (a longest common subsequence), then equal keys that moved, then leftovers between the same two
 * in-order matches, paired in order, so an item edited in place keeps its identity. `compatible`
 * limits the last two steps.
 */
export function pair<T>(
	previous: T[],
	next: T[],
	key: (item: T) => string,
	compatible: (old: T, item: T) => boolean = () => true
): (T | undefined)[] {
	const oldKeys = previous.map(key);
	const newKeys = next.map(key);
	const cols = next.length + 1;
	// lengths[i * cols + j]: LCS length of oldKeys[i..] and newKeys[j..].
	const lengths = new Uint32Array((previous.length + 1) * cols);
	const length = (i: number, j: number) => lengths[i * cols + j] as number;
	for (let i = previous.length - 1; i >= 0; i--) {
		for (let j = next.length - 1; j >= 0; j--) {
			lengths[i * cols + j] =
				oldKeys[i] === newKeys[j]
					? length(i + 1, j + 1) + 1
					: Math.max(length(i + 1, j), length(i, j + 1));
		}
	}

	const result: (T | undefined)[] = new Array(next.length).fill(undefined);
	const used = new Set<number>();
	// The gap of a leftover item: how many in-order matches come before it.
	const oldGap: number[] = [];
	const newGap: number[] = [];
	let matched = 0;
	let i = 0;
	let j = 0;
	while (i < previous.length || j < next.length) {
		if (i < previous.length && j < next.length && oldKeys[i] === newKeys[j]) {
			result[j++] = previous[i];
			used.add(i++);
			matched++;
		} else if (j >= next.length || (i < previous.length && length(i + 1, j) >= length(i, j + 1))) {
			oldGap[i++] = matched;
		} else {
			newGap[j++] = matched;
		}
	}

	const fits = (oldIndex: number, newIndex: number) =>
		!used.has(oldIndex) && compatible(previous[oldIndex] as T, next[newIndex] as T);
	for (let n = 0; n < next.length; n++) {
		if (result[n] !== undefined) continue;
		const moved = oldKeys.findIndex((oldKey, o) => oldKey === newKeys[n] && fits(o, n));
		if (moved !== -1) {
			result[n] = previous[moved];
			used.add(moved);
		}
	}

	const leftovers = new Map<number, number[]>();
	previous.forEach((_, o) => {
		if (used.has(o)) return;
		const gap = oldGap[o] as number;
		leftovers.set(gap, [...(leftovers.get(gap) ?? []), o]);
	});
	for (let n = 0; n < next.length; n++) {
		if (result[n] !== undefined) continue;
		const old = leftovers.get(newGap[n] as number)?.shift();
		if (old !== undefined && fits(old, n)) {
			result[n] = previous[old];
			used.add(old);
		}
	}
	return result;
}
