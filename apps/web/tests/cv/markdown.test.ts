import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { fromMarkdown, pair, toMarkdown, type MarkdownResult } from '#lib/cv/markdown.ts';
import type { CvContent, DateRange, Section, SectionKind } from '#lib/cv/types.ts';

const FIXTURES = join(import.meta.dirname, '../../../../templates/fixtures');

type Loose = Record<string, unknown>;

/** Fill the model's defaults, as the api returns content (fixtures leave defaults out). */
function complete(raw: Loose): CvContent {
	const bullets = (list: unknown) =>
		((list as Loose[] | undefined) ?? []).map((b) => ({
			id: b.id as string,
			text: b.text as string,
			source_id: (b.source_id as string | null | undefined) ?? null
		}));
	const basics = raw.basics as Loose;
	return {
		schema_version: 1,
		basics: {
			name: basics.name as string,
			headline: (basics.headline as string) ?? '',
			email: (basics.email as string) ?? '',
			phone: (basics.phone as string) ?? '',
			location: (basics.location as string) ?? '',
			links: (basics.links as { label: string; url: string }[]) ?? []
		},
		summary: (raw.summary as string) ?? '',
		sections: (raw.sections as Loose[]).map((s) => ({
			id: s.id as string,
			kind: s.kind as SectionKind,
			title: s.title as string,
			experience: ((s.experience as Loose[]) ?? []).map((e) => ({
				id: e.id as string,
				org: e.org as string,
				role: e.role as string,
				location: (e.location as string) ?? '',
				dates: {
					start: (e.dates as Loose).start as string,
					end: ((e.dates as Loose).end as string) ?? null
				},
				stack: (e.stack as string[]) ?? [],
				bullets: bullets(e.bullets),
				engagements: ((e.engagements as Loose[]) ?? []).map((g) => ({
					id: g.id as string,
					name: g.name as string,
					label: (g.label as string) ?? 'Client',
					location: (g.location as string) ?? '',
					dates: g.dates
						? {
								start: (g.dates as Loose).start as string,
								end: ((g.dates as Loose).end as string) ?? null
							}
						: null,
					bullets: bullets(g.bullets)
				}))
			})),
			projects: ((s.projects as Loose[]) ?? []).map((p) => ({
				id: p.id as string,
				name: p.name as string,
				url: (p.url as string) ?? null,
				status: (p.status as string) ?? '',
				year: (p.year as string) ?? '',
				bullets: bullets(p.bullets)
			})),
			education: ((s.education as Loose[]) ?? []).map((e) => ({
				id: e.id as string,
				institution: e.institution as string,
				degree: e.degree as string,
				location: (e.location as string) ?? '',
				dates: {
					start: (e.dates as Loose).start as string,
					end: ((e.dates as Loose).end as string) ?? null
				}
			})),
			skills: ((s.skills as Loose[]) ?? []).map((g) => ({
				id: g.id as string,
				label: g.label as string,
				items: g.items as string[]
			})),
			certifications: ((s.certifications as Loose[]) ?? []).map((c) => ({
				id: c.id as string,
				name: c.name as string,
				issuer: c.issuer as string,
				date: (c.date as string) ?? ''
			})),
			custom: bullets(s.custom)
		}))
	};
}

function fixture(name: string): CvContent {
	return complete(JSON.parse(readFileSync(join(FIXTURES, name), 'utf8')) as Loose);
}

function parsed(result: MarkdownResult): CvContent {
	if (!result.ok) throw new Error(JSON.stringify(result.errors));
	return result.content;
}

function errorsOf(result: MarkdownResult): { line: number; message: string }[] {
	if (result.ok) throw new Error('expected errors');
	return result.errors;
}

function section(kind: SectionKind, title: string, fill: Partial<Section> = {}): Section {
	return {
		id: `s-${title}`,
		kind,
		title,
		experience: [],
		projects: [],
		education: [],
		skills: [],
		certifications: [],
		custom: [],
		...fill
	};
}

function cv(fill: Partial<CvContent> = {}): CvContent {
	return {
		schema_version: 1,
		basics: { name: 'Ama', headline: '', email: '', phone: '', location: '', links: [] },
		summary: '',
		sections: [],
		...fill
	};
}

const bullet = (id: string, text: string, source_id: string | null = null) => ({
	id,
	text,
	source_id
});

const PROFILE_FIXTURES = readdirSync(FIXTURES).filter((name) => /^profile-.+\.json$/.test(name));

describe('round trip', () => {
	it('covers every profile fixture', () => {
		expect(PROFILE_FIXTURES).toEqual([
			'profile-edge.json',
			'profile-long.json',
			'profile-sample.json'
		]);
	});

	it.each(PROFILE_FIXTURES)('keeps %s unchanged', (name) => {
		const content = fixture(name);

		expect(parsed(fromMarkdown(toMarkdown(content), content))).toEqual(content);
	});

	it.each(PROFILE_FIXTURES)('reads %s back to the same text with no earlier content', (name) => {
		const content = fixture(name);

		// Every id is new, but the Markdown written from it is the same.
		const again = parsed(fromMarkdown(toMarkdown(content), cv()));

		expect(toMarkdown(again)).toBe(toMarkdown(content));
	});

	it('keeps an empty end date empty, and "present" as none', () => {
		const dates = (start: string, end: string | null) =>
			cv({
				sections: [
					section('education', 'Education', {
						education: [
							{ id: 'e1', institution: 'Uni', degree: '', location: '', dates: { start, end } }
						]
					})
				]
			});

		for (const [start, end] of [
			['2019', null],
			['2019', ''],
			['', ''],
			['', '2021'],
			['2019', '2021'],
			['2019', '2019']
		] as const) {
			const content = dates(start, end);

			expect(parsed(fromMarkdown(toMarkdown(content), content))).toEqual(content);
		}
		const typed = dates('2019', 'Present');
		expect(parsed(fromMarkdown(toMarkdown(typed), typed))).toEqual(dates('2019', null));
	});

	it('writes the documented format', () => {
		const content = cv({
			basics: {
				name: 'Ama Owusu-Mensah',
				headline: 'Senior data engineer',
				email: 'ama@example.com',
				phone: '',
				location: 'Accra, Ghana',
				links: [{ label: 'GitHub', url: 'https://github.com/ama' }]
			},
			summary: 'Data engineer with **8 years**.',
			sections: [
				section('experience', 'Experience', {
					experience: [
						{
							id: 'e1',
							org: 'Acme Bank',
							role: 'Senior data engineer',
							location: 'Accra',
							dates: { start: '2021-03', end: null },
							stack: ['Python', 'Spark'],
							bullets: [bullet('b1', 'Cut delay by [[hours saved]].')],
							engagements: [
								{
									id: 'g1',
									name: 'Big Telco',
									label: 'Client',
									location: '',
									dates: { start: '2022-01', end: '2023-06' },
									bullets: [bullet('b2', 'Built the billing model.')]
								}
							]
						}
					]
				}),
				section('skills', 'Skills', {
					skills: [{ id: 'k1', label: 'Languages', items: ['Python', 'SQL'] }]
				}),
				section('education', 'Education', {
					education: [
						{
							id: 'd1',
							institution: 'University of Ghana',
							degree: 'BSc',
							location: '',
							dates: { start: '2016', end: '2016' }
						}
					]
				}),
				section('custom', 'Volunteering', { custom: [bullet('c1', 'Mentor.')] })
			]
		});

		expect(toMarkdown(content)).toBe(
			[
				'# Ama Owusu-Mensah',
				'Headline: Senior data engineer',
				'Email: ama@example.com',
				'Location: Accra, Ghana',
				'Link: [GitHub](https://github.com/ama)',
				'',
				'Data engineer with **8 years**.',
				'',
				'## Experience {experience}',
				'',
				'### Acme Bank',
				'Role: Senior data engineer',
				'Location: Accra',
				'Dates: 2021-03 to present',
				'Stack: Python, Spark',
				'',
				'- Cut delay by [[hours saved]].',
				'',
				'#### Big Telco',
				'Dates: 2022-01 to 2023-06',
				'',
				'- Built the billing model.',
				'',
				'## Skills {skills}',
				'',
				'- Languages: Python, SQL',
				'',
				'## Education {education}',
				'',
				'### University of Ghana',
				'Degree: BSc',
				'Dates: 2016',
				'',
				'## Volunteering {custom}',
				'',
				'- Mentor.',
				''
			].join('\n')
		);
		expect(parsed(fromMarkdown(toMarkdown(content), content))).toEqual(content);
	});

	it('escapes what would read as structure', () => {
		const content = cv({
			summary: '# not a heading\n\\# a backslash first\n\\\\ two\n\nplain \\ text',
			sections: [
				section('custom', 'Ends like a kind {skills}', {
					custom: [bullet('c1', 'first line\n\n  indented\n- dash line\n## hash line')]
				}),
				section('experience', '', {
					experience: [
						{
							id: 'e1',
							org: '',
							role: 'Role: with colon',
							location: '',
							dates: { start: '', end: '2020' },
							stack: ['C, C++', 'back\\slash\\', 'a\\,b', 'Docker (Compose, Swarm)'],
							bullets: [bullet('b1', '')],
							engagements: [
								{ id: 'g1', name: 'No label', label: '', location: '', dates: null, bullets: [] },
								{
									id: 'g2',
									name: 'Agency',
									label: 'Agency',
									location: '',
									dates: null,
									bullets: []
								}
							]
						}
					]
				}),
				section('skills', 'Skills', {
					skills: [
						{ id: 'k1', label: 'Time: zones \\', items: [] },
						{ id: 'k2', label: '', items: ['a'] }
					]
				})
			],
			basics: {
				name: '',
				headline: '',
				email: '',
				phone: '',
				location: '',
				links: [{ label: 'Docs [v2]', url: 'https://example.com/a_(b)' }]
			}
		});

		const markdown = toMarkdown(content);

		expect(markdown).toContain(
			'Stack: C\\, C++, back\\slash\\\\, a\\\\\\,b, Docker (Compose\\, Swarm)'
		);
		expect(markdown).toContain('\\# not a heading');
		expect(markdown).toContain('## Ends like a kind {skills} {custom}');
		expect(parsed(fromMarkdown(markdown, content))).toEqual(content);
	});
});

describe('reading', () => {
	const base = cv();

	it('accepts loose but clear input', () => {
		const content = parsed(
			fromMarkdown(
				[
					'',
					'# Ama',
					'EMAIL:ama@example.com',
					'## Work {experience}',
					'### Acme',
					'  role:  Engineer  ',
					'Dates: 2019',
					'* Did things.',
					'## Notes',
					'- Free text.'
				].join('\r\n'),
				base
			)
		);

		expect(content.basics.email).toBe('ama@example.com');
		const [work, notes] = content.sections;
		expect(work?.experience[0]).toMatchObject({
			org: 'Acme',
			role: 'Engineer',
			dates: { start: '2019', end: '2019' },
			bullets: [{ text: 'Did things.', source_id: null }]
		});
		expect(notes).toMatchObject({
			kind: 'custom',
			title: 'Notes',
			custom: [{ text: 'Free text.' }]
		});
	});

	it.each([
		['2019 to 2021', { start: '2019', end: '2021' }],
		['2019 to Present', { start: '2019', end: null }],
		['2019 to', { start: '2019', end: '' }],
		['to', { start: '', end: '' }],
		['to 2021', { start: '', end: '2021' }],
		['Toronto 2019', { start: 'Toronto 2019', end: 'Toronto 2019' }]
	])('reads Dates: %s', (value, dates) => {
		const text = `# A\n## E {education}\n### Uni\nDates: ${value}\n`;

		expect(parsed(fromMarkdown(text, base)).sections[0]?.education[0]?.dates).toEqual(dates);
	});

	it.each([
		['Ama', 1, 'Start with the name as a # heading'],
		['', 1, 'Start with the name as a # heading'],
		['# A\n# B', 2, 'Use # only once'],
		['# A\n### Acme', 2, 'Start a section with a ## heading first'],
		['# A\n## E {experience}\n- early', 3, 'Add a ### heading for the entry before its bullets'],
		['# A\n## E {experience}\nRole: x', 3, 'Add a ### heading for the entry first'],
		[
			'# A\n## E {experience}\n### Acme\nTeam: x',
			4,
			'Unknown field "Team". Use Role, Location, Dates, Stack.'
		],
		['# A\n## E {experience}\n### Acme\n- b\nRole: x', 5, 'Put fields right under the heading'],
		[
			'# A\n## E {experience}\n### Acme\nRole: x\nRole: y',
			5,
			'Role is already set for this entry.'
		],
		['# A\n## E {experience}\n### Acme\nloose text', 4, 'Start bullets with "- "'],
		['# A\n## E {education}\n### Uni\n- b', 4, 'Education entries have no bullets.'],
		['# A\n## C {certifications}\n### AWS\n- b', 4, 'Certifications have no bullets.'],
		['# A\n## P {projects}\n### Site\nURL: example.com', 4, 'Enter a full link'],
		['# A\nLink: https://example.com', 2, 'Write links as'],
		['# A\nLink: [Site](ftp://example.com)', 2, 'Enter a full link'],
		['# A\nEmail: a\nEmail: b', 3, 'Email is already set above.'],
		['# A\n## S {skills}\n- Python, Go', 3, 'Write skills as "- Label: item, item".'],
		['# A\n## S {skills}\n### Group', 3, 'Skills have no ### entries'],
		['# A\n## S {skills}\nLanguages: Go', 3, 'Write skills as'],
		['# A\n## C\n### Entry', 3, 'Custom sections hold bullets only'],
		['# A\n## C\ntext', 3, 'Start each line of a custom section with "- "'],
		['# A\n## P {projects}\n#### Client', 3, 'Use #### only for a client']
	])('reports %j at line %i', (text, line, message) => {
		const [error] = errorsOf(fromMarkdown(text, base));

		expect(error?.line).toBe(line);
		expect(error?.message).toContain(message);
	});

	it('reports every error, not only the first', () => {
		const errors = errorsOf(fromMarkdown('# A\n## E {experience}\nRole: x\n- y\n', base));

		expect(errors.map((e) => e.line)).toEqual([3, 4]);
	});
});

describe('identity', () => {
	const previous = cv({
		sections: [
			section('custom', 'One', {
				id: 's1',
				custom: [
					bullet('b1', 'Alpha', 'p1'),
					bullet('b2', 'Beta', 'p2'),
					bullet('b3', 'Gamma', 'p3')
				]
			}),
			section('skills', 'Two', {
				id: 's2',
				skills: [{ id: 'k1', label: 'Languages', items: ['Go'] }]
			})
		]
	});

	function ids(content: CvContent) {
		return content.sections.map((s) => ({
			id: s.id,
			bullets: s.custom.map((b) => [b.id, b.text, b.source_id]),
			skills: s.skills.map((k) => k.id)
		}));
	}

	it('keeps ids of unchanged and edited bullets, and links new ones to nothing', () => {
		const text = toMarkdown(previous)
			.replace('- Alpha', '- New first\n- Alpha')
			.replace('- Beta', '- Beta, edited')
			.replace('- Gamma\n', '');

		const [one] = ids(parsed(fromMarkdown(text, previous)));

		expect(one?.id).toBe('s1');
		expect(one?.bullets[0]?.[0]).not.toMatch(/^b\d$/);
		expect(one?.bullets.slice(1)).toEqual([
			['b1', 'Alpha', 'p1'],
			['b2', 'Beta, edited', 'p2']
		]);
	});

	it('keeps section ids when sections move, and gives new sections new ids', () => {
		const [first, second] = toMarkdown(previous).split('\n## ').slice(1);
		const text = `# Ama\n\n## ${second}\n## ${first}\n## Added {custom}\n`;

		const sections = ids(parsed(fromMarkdown(text, previous)));

		expect(sections.map((s) => s.id).slice(0, 2)).toEqual(['s2', 's1']);
		expect(sections[0]?.skills).toEqual(['k1']);
		expect(sections[2]?.id).toMatch(/^[0-9a-f]{12}$/);
	});

	it('does not carry a section id across kinds', () => {
		const text = toMarkdown(previous).replace('## Two {skills}', '## Two {custom}');

		const sections = ids(parsed(fromMarkdown(text, previous)));

		expect(sections[1]?.id).not.toBe('s2');
	});

	it('pairs by longest common subsequence, then in place', () => {
		const result = pair(['a', 'b', 'c', 'd'], ['x', 'b', 'y', 'd', 'z'], (s) => s);

		expect(result).toEqual(['a', 'b', 'c', 'd', undefined]);
	});

	it('follows items that moved', () => {
		expect(pair(['a', 'b', 'c'], ['c', 'a', 'b'], (s) => s)).toEqual(['c', 'a', 'b']);
		expect(pair(['a', 'b'], ['b', 'x', 'a'], (s) => s)).toEqual(['b', undefined, 'a']);
	});
});

describe('random content', () => {
	// mulberry32: a small seeded generator, so failures reproduce.
	function random(seed: number) {
		return () => {
			seed = (seed + 0x6d2b79f5) | 0;
			let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
			t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
			return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
		};
	}

	const TRICKY = [
		'a',
		'b',
		'Z',
		' ',
		' ',
		',',
		':',
		'\\',
		'#',
		'[',
		']',
		'(',
		')',
		'{',
		'}',
		'*',
		'-',
		'é',
		'1',
		'\t'
	];
	const KINDS: SectionKind[] = [
		'experience',
		'projects',
		'education',
		'skills',
		'certifications',
		'custom'
	];

	function generator(seed: number) {
		const next = random(seed);
		const int = (max: number) => Math.floor(next() * max);
		const pick = <T>(list: readonly T[]) => list[int(list.length)] as T;
		const many = <T>(max: number, make: () => T) => Array.from({ length: int(max + 1) }, make);
		const raw = (max: number, extra: string[] = []) =>
			Array.from({ length: int(max) }, () => pick([...TRICKY, ...extra])).join('');
		const line = (max = 12) => raw(max).trim();
		const lines = (max = 4) =>
			many(max, () => raw(10))
				.join('\n')
				.trim();
		const listItems = () => many(3, () => line(8)).filter(Boolean);
		// No "o", so no value holds the word "to", which separates the two dates.
		const date = () => line(6).replace(/o/g, '');
		const dates = (): DateRange => {
			const start = date();
			const end = date();
			return { start, end: end && next() < 0.7 ? end : null };
		};
		const url = () => `https://example.com/${raw(6, []).replace(/[^a-z0-9]/gi, '')}`;
		let ids = 0;
		const id = () => `id${ids++}`;
		const bullets = () => many(3, () => bullet(id(), lines(), next() < 0.5 ? id() : null));

		return (): CvContent =>
			cv({
				basics: {
					name: line(),
					headline: line(),
					email: line(),
					phone: line(),
					location: line(),
					links: many(2, () => ({ label: line(), url: url() }))
				},
				summary: many(4, () => pick(['# h', '\\# e', '\\\\ x', '## s', raw(10)]))
					.join('\n')
					.trim(),
				sections: many(4, () => {
					const kind = pick(KINDS);
					return section(kind, line(), {
						id: id(),
						experience:
							kind === 'experience'
								? many(2, () => ({
										id: id(),
										org: line(),
										role: line(),
										location: line(),
										dates: dates(),
										stack: listItems(),
										bullets: bullets(),
										engagements: many(2, () => {
											const engagementDates = dates();
											return {
												id: id(),
												name: line(),
												label: pick(['Client', '', line()]),
												location: line(),
												dates:
													engagementDates.start || engagementDates.end ? engagementDates : null,
												bullets: bullets()
											};
										})
									}))
								: [],
						projects:
							kind === 'projects'
								? many(2, () => ({
										id: id(),
										name: line(),
										url: next() < 0.5 ? url() : null,
										status: line(),
										year: line(),
										bullets: bullets()
									}))
								: [],
						education:
							kind === 'education'
								? many(2, () => ({
										id: id(),
										institution: line(),
										degree: line(),
										location: line(),
										dates: dates()
									}))
								: [],
						skills:
							kind === 'skills'
								? many(3, () => ({ id: id(), label: line(), items: listItems() }))
								: [],
						certifications:
							kind === 'certifications'
								? many(2, () => ({ id: id(), name: line(), issuer: line(), date: line() }))
								: [],
						custom: kind === 'custom' ? bullets() : []
					});
				})
			});
	}

	it('survives a round trip for 300 generated CVs', () => {
		const make = generator(20261017);
		for (let run = 0; run < 300; run++) {
			const content = make();
			const markdown = toMarkdown(content);

			expect(parsed(fromMarkdown(markdown, content)), markdown).toEqual(content);
		}
	});
});
