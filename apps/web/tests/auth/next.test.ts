import { describe, expect, it } from 'vitest';
import { afterSignIn, nextPath, signInPath, withNext } from '#lib/auth/next.ts';

const at = (path: string) => new URL(path, 'https://cvitae.example');

describe('coming back after sign-in', () => {
	it('follows ?next= to an app page', () => {
		expect(afterSignIn(at('/?next=%2Fapp%2Fextension'))).toBe('/app/extension');
		expect(afterSignIn(at('/?next=/app/tailor?job=j1'))).toBe('/app/tailor?job=j1');
	});

	it('goes to Documents otherwise', () => {
		expect(afterSignIn(at('/'))).toBe('/app/documents');
	});

	it.each([
		'https://evil.example/app/x',
		'//evil.example/app/x',
		'/\\evil.example/app/x',
		'/',
		'/auth/complete',
		'/application',
		'javascript:alert(1)'
	])('never follows %s', (next) => {
		expect(nextPath(at(`/?next=${encodeURIComponent(next)}`))).toBeNull();
	});

	it('remembers the page a signed-out user was sent away from', () => {
		expect(signInPath(at('/app/extension'))).toBe('/login?next=%2Fapp%2Fextension');
		expect(signInPath(at('/app/tailor?job=j1'))).toBe('/login?next=%2Fapp%2Ftailor%3Fjob%3Dj1');
		expect(signInPath(at('/app/documents'))).toBe('/');
	});

	it('carries the page in the email sign-in link', () => {
		expect(withNext('https://x/auth/complete', '/app/settings')).toBe(
			'https://x/auth/complete?next=%2Fapp%2Fsettings'
		);
		expect(withNext('https://x/auth/complete', null)).toBe('https://x/auth/complete');
	});
});
