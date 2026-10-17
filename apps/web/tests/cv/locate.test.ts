import { describe, expect, it } from 'vitest';
import { newSection } from '#lib/cv/factory.ts';
import { describeLocation } from '#lib/cv/locate.ts';
import type { CvContent } from '#lib/cv/types.ts';

function content(): CvContent {
	const experience = newSection('experience');
	experience.experience.push({
		id: 'r1',
		org: 'Northwind',
		role: 'Engineer',
		location: '',
		dates: { start: '2021', end: null },
		stack: [],
		bullets: [{ id: 'b1', text: '[[n]] users', source_id: null }],
		engagements: [
			{
				id: 'g1',
				name: 'Harbour Bank',
				label: 'Client',
				location: '',
				dates: null,
				bullets: [{ id: 'b2', text: '[[x]]', source_id: null }]
			}
		]
	});
	const projects = newSection('projects');
	projects.projects.push({
		id: 'p1',
		name: 'Ledgerline',
		url: null,
		status: '',
		year: '',
		bullets: [{ id: 'b3', text: '[[y]]', source_id: null }]
	});
	const custom = newSection('custom');
	custom.title = 'Awards';
	custom.custom.push({ id: 'b4', text: '[[z]]', source_id: null });
	return {
		schema_version: 1,
		basics: { name: '', headline: '', email: '', phone: '', location: '', links: [] },
		summary: '[[domain]]',
		sections: [experience, projects, custom]
	};
}

describe('describeLocation', () => {
	it.each([
		[null, 'Summary'],
		['b1', 'Experience, Northwind'],
		['b2', 'Experience, Harbour Bank'],
		['b3', 'Projects, Ledgerline'],
		['b4', 'Awards'],
		['gone', 'A bullet that no longer exists']
	])('places bullet %s in %s', (bulletId, expected) => {
		expect(describeLocation(content(), { text: 'x', bullet_id: bulletId })).toBe(expected);
	});
});
