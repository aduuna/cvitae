import type {
	Bullet,
	CertificationItem,
	EducationItem,
	Engagement,
	ExperienceItem,
	Link,
	ProjectItem,
	Section,
	SectionKind,
	SkillGroup
} from './types';

/** A random 12-character hex id, the same format as cvcore.ids.new_id. */
export function newId(): string {
	const bytes = crypto.getRandomValues(new Uint8Array(6));
	return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

const objectKeys = new WeakMap<object, string>();

/** A stable key for an item without an id (links), for keyed lists. */
export function objectKey(item: object): string {
	let key = objectKeys.get(item);
	if (!key) {
		key = newId();
		objectKeys.set(item, key);
	}
	return key;
}

/** Section kinds in the order the "Add section" menu offers them, with default titles. */
export const sectionKinds: { kind: SectionKind; title: string }[] = [
	{ kind: 'experience', title: 'Experience' },
	{ kind: 'projects', title: 'Projects' },
	{ kind: 'education', title: 'Education' },
	{ kind: 'skills', title: 'Skills' },
	{ kind: 'certifications', title: 'Certifications' },
	{ kind: 'custom', title: 'Custom section' }
];

export function newSection(kind: SectionKind): Section {
	const title = sectionKinds.find((entry) => entry.kind === kind)?.title ?? 'Section';
	return {
		id: newId(),
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

export function newBullet(): Bullet {
	return { id: newId(), text: '', source_id: null };
}

export function newLink(): Link {
	return { label: '', url: '' };
}

export function newExperience(): ExperienceItem {
	return {
		id: newId(),
		org: '',
		role: '',
		location: '',
		dates: { start: '', end: null },
		stack: [],
		bullets: [newBullet()],
		engagements: []
	};
}

export function newEngagement(): Engagement {
	return {
		id: newId(),
		name: '',
		label: 'Client',
		location: '',
		dates: null,
		bullets: [newBullet()]
	};
}

export function newProject(): ProjectItem {
	return { id: newId(), name: '', url: null, status: '', year: '', bullets: [newBullet()] };
}

export function newEducation(): EducationItem {
	return {
		id: newId(),
		institution: '',
		degree: '',
		location: '',
		dates: { start: '', end: null }
	};
}

export function newSkillGroup(): SkillGroup {
	return { id: newId(), label: '', items: [] };
}

export function newCertification(): CertificationItem {
	return { id: newId(), name: '', issuer: '', date: '' };
}

/** Move an item within a list in place. Returns false when the move goes nowhere. */
export function moveItem<T>(list: T[], from: number, to: number): boolean {
	if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) return false;
	const [item] = list.splice(from, 1);
	list.splice(to, 0, item as T);
	return true;
}

/** Split comma-separated text into trimmed, non-empty items. */
export function splitList(text: string): string[] {
	return text
		.split(',')
		.map((item) => item.trim())
		.filter(Boolean);
}
