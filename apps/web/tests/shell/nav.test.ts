import { describe, expect, it } from 'vitest';
import { isActive, navItems } from '#lib/components/shell/nav.ts';

describe('navItems', () => {
	it('matches the product navigation', () => {
		expect(navItems.map((item) => [item.label, item.href, item.icon])).toEqual([
			['Documents', '/app/documents', 'documents'],
			['Profiles', '/app/profiles', 'profiles'],
			['Tailor', '/app/tailor', 'tailor'],
			['Templates', '/app/templates', 'templates'],
			['Settings', '/app/settings', 'settings']
		]);
	});
});

describe('isActive', () => {
	const documents = navItems[0]!;

	it.each([
		['/app/documents', true],
		['/app/documents/abc', true],
		['/app/documents-archive', false],
		['/app/profiles', false]
	])('%s -> %s', (pathname, expected) => {
		expect(isActive(documents, pathname)).toBe(expected);
	});
});
