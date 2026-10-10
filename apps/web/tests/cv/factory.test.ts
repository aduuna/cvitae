import { describe, expect, it } from 'vitest';
import {
	moveItem,
	newExperience,
	newId,
	newSection,
	objectKey,
	sectionKinds,
	splitList
} from '#lib/cv/factory.ts';

describe('newId', () => {
	it('makes 12-character hex ids like cvcore', () => {
		const ids = new Set(Array.from({ length: 50 }, newId));
		expect(ids.size).toBe(50);
		for (const id of ids) expect(id).toMatch(/^[0-9a-f]{12}$/);
	});
});

describe('newSection', () => {
	it.each(sectionKinds)(
		'starts a $kind section titled $title with empty lists',
		({ kind, title }) => {
			const section = newSection(kind);
			expect(section).toMatchObject({ kind, title, experience: [], skills: [], custom: [] });
		}
	);
});

describe('newExperience', () => {
	it('is an open-ended role with one empty bullet', () => {
		const role = newExperience();
		expect(role.dates).toEqual({ start: '', end: null });
		expect(role.bullets).toHaveLength(1);
		expect(role.bullets[0]?.text).toBe('');
	});
});

describe('moveItem', () => {
	it('moves in place', () => {
		const list = ['a', 'b', 'c', 'd'];
		expect(moveItem(list, 0, 2)).toBe(true);
		expect(list).toEqual(['b', 'c', 'a', 'd']);
		expect(moveItem(list, 3, 0)).toBe(true);
		expect(list).toEqual(['d', 'b', 'c', 'a']);
	});

	it.each([
		[1, 1],
		[0, -1],
		[3, 4],
		[-1, 0]
	])('ignores a move from %i to %i', (from, to) => {
		const list = ['a', 'b', 'c', 'd'];
		expect(moveItem(list, from, to)).toBe(false);
		expect(list).toEqual(['a', 'b', 'c', 'd']);
	});
});

describe('splitList', () => {
	it.each([
		['Python, SQL ,  Go', ['Python', 'SQL', 'Go']],
		['Python,', ['Python']],
		[' , ,', []],
		['', []]
	])('splits %j', (text, expected) => {
		expect(splitList(text)).toEqual(expected);
	});
});

describe('objectKey', () => {
	it('gives each object one stable key', () => {
		const a = { label: 'GitHub' };
		const b = { label: 'GitHub' };
		expect(objectKey(a)).toBe(objectKey(a));
		expect(objectKey(a)).not.toBe(objectKey(b));
	});
});
