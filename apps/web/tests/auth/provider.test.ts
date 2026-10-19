import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthError, DEV_USER } from '#lib/api/client.ts';
import { authErrorFrom, devProvider, firebaseProvider } from '#lib/auth/provider.ts';

const firebase = vi.hoisted(() => ({
	user: null as { email: string | null; getIdToken: () => Promise<string> } | null,
	listener: null as ((user: unknown) => void) | null,
	initializeApp: vi.fn(() => ({ name: 'app' })),
	signInWithPopup: vi.fn(async () => {}),
	sendSignInLinkToEmail: vi.fn(async () => {}),
	signInWithEmailLink: vi.fn(async () => {}),
	signInWithEmailAndPassword: vi.fn(async () => {}),
	signOut: vi.fn(async () => {}),
	setCustomParameters: vi.fn()
}));

vi.mock('firebase/app', () => ({ initializeApp: firebase.initializeApp }));
vi.mock('firebase/auth', () => {
	const auth = {
		get currentUser() {
			return firebase.user;
		}
	};
	return {
		getAuth: () => auth,
		onAuthStateChanged: (_: unknown, listener: (user: unknown) => void) => {
			firebase.listener = listener;
			listener(firebase.user);
		},
		GoogleAuthProvider: class {
			setCustomParameters = firebase.setCustomParameters;
		},
		signInWithPopup: firebase.signInWithPopup,
		sendSignInLinkToEmail: firebase.sendSignInLinkToEmail,
		isSignInWithEmailLink: (_: unknown, url: string) => url.includes('oobCode='),
		signInWithEmailLink: firebase.signInWithEmailLink,
		signInWithEmailAndPassword: firebase.signInWithEmailAndPassword,
		signOut: firebase.signOut
	};
});

const CONFIG = { api_key: 'key', auth_domain: 'p.firebaseapp.com', project_id: 'p', app_id: 'a' };

describe('devProvider', () => {
	beforeEach(() => localStorage.clear());
	afterEach(() => vi.restoreAllMocks());

	it('starts signed in as the dev user', async () => {
		const provider = devProvider();
		const seen: (string | null)[] = [];

		provider.watch((email) => seen.push(email));

		expect(seen).toEqual([DEV_USER]);
		expect(await provider.headers()).toEqual({ 'X-Dev-User': DEV_USER });
		expect(provider.isEmailLink('http://x/?oobCode=1')).toBe(false);
	});

	it('signs out until Continue with Google, across reloads', async () => {
		const provider = devProvider();
		const seen: (string | null)[] = [];
		provider.watch((email) => seen.push(email));

		await provider.signOut();

		expect(seen).toEqual([DEV_USER, null]);
		expect(await provider.headers()).toEqual({});
		// A reload makes a new provider; it remembers the sign-out.
		const reloaded = devProvider();
		const afterReload: (string | null)[] = [];
		reloaded.watch((email) => afterReload.push(email));
		expect(afterReload).toEqual([null]);

		await reloaded.signInWithGoogle();

		expect(afterReload).toEqual([null, DEV_USER]);
		expect(await reloaded.headers()).toEqual({ 'X-Dev-User': DEV_USER });
		expect(localStorage.length).toBe(0);
	});

	it('signs out for the page when storage is blocked', async () => {
		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new DOMException('blocked', 'SecurityError');
		});
		const provider = devProvider();
		const seen: (string | null)[] = [];
		provider.watch((email) => seen.push(email));

		await provider.signOut();

		expect(seen).toEqual([DEV_USER, null]);
	});

	it('does not send email links', async () => {
		const provider = devProvider();

		await expect(provider.sendEmailLink('ada@example.com', 'http://x')).rejects.toThrow(
			new AuthError('Email links are not sent in local development. Use Continue with Google.')
		);
	});

	it('does not take passwords', async () => {
		const provider = devProvider();

		await expect(provider.signInWithPassword('ada@example.com', 'secret')).rejects.toThrow(
			new AuthError('Passwords are not used in local development. Use Continue with Google.')
		);
	});
});

describe('authErrorFrom', () => {
	it.each([
		[
			'auth/popup-closed-by-user',
			'The Google window was closed before sign-in finished. Try again.'
		],
		[
			'auth/expired-action-code',
			'This sign-in link has expired or was already used. Request a new one.'
		],
		['auth/invalid-credential', 'The email or password is wrong. Check both and try again.'],
		['auth/unknown-thing', 'Sign-in failed. Try again.']
	])('explains %s', (code, message) => {
		expect(authErrorFrom({ code }).message).toBe(message);
	});

	it('has a generic message for non-Firebase errors', () => {
		expect(authErrorFrom(new Error('x')).message).toBe('Sign-in failed. Try again.');
	});
});

describe('firebaseProvider', () => {
	beforeEach(() => {
		firebase.user = null;
		vi.clearAllMocks();
	});

	it('initialises Firebase with the web config', async () => {
		await firebaseProvider(CONFIG);

		expect(firebase.initializeApp).toHaveBeenCalledWith({
			apiKey: 'key',
			authDomain: 'p.firebaseapp.com',
			projectId: 'p',
			appId: 'a'
		});
	});

	it('reports the signed-in email and sends its ID token', async () => {
		const provider = await firebaseProvider(CONFIG);
		const seen: (string | null)[] = [];
		provider.watch((email) => seen.push(email));

		expect(await provider.headers()).toEqual({});
		firebase.user = { email: 'ada@example.com', getIdToken: async () => 'id-token' };
		firebase.listener?.(firebase.user);

		expect(seen).toEqual([null, 'ada@example.com']);
		expect(await provider.headers()).toEqual({ Authorization: 'Bearer id-token' });
	});

	it('signs in with a Google pop-up that asks which account', async () => {
		const provider = await firebaseProvider(CONFIG);

		await provider.signInWithGoogle();

		expect(firebase.setCustomParameters).toHaveBeenCalledWith({ prompt: 'select_account' });
		expect(firebase.signInWithPopup).toHaveBeenCalledOnce();
	});

	it('sends and completes email links', async () => {
		const provider = await firebaseProvider(CONFIG);

		await provider.sendEmailLink('ada@example.com', 'http://localhost/auth/complete');
		expect(firebase.sendSignInLinkToEmail).toHaveBeenCalledWith(
			expect.anything(),
			'ada@example.com',
			{ url: 'http://localhost/auth/complete', handleCodeInApp: true }
		);

		expect(provider.isEmailLink('http://localhost/auth/complete?oobCode=1')).toBe(true);
		await provider.completeEmailLink('ada@example.com', 'http://localhost/?oobCode=1');
		expect(firebase.signInWithEmailLink).toHaveBeenCalledWith(
			expect.anything(),
			'ada@example.com',
			'http://localhost/?oobCode=1'
		);

		await provider.signOut();
		expect(firebase.signOut).toHaveBeenCalledOnce();
	});

	it('signs in with a password', async () => {
		const provider = await firebaseProvider(CONFIG);

		await provider.signInWithPassword('review@example.com', 'secret');

		expect(firebase.signInWithEmailAndPassword).toHaveBeenCalledWith(
			expect.anything(),
			'review@example.com',
			'secret'
		);
	});

	it('turns Firebase errors into messages', async () => {
		firebase.signInWithPopup.mockRejectedValueOnce({ code: 'auth/popup-blocked' });
		const provider = await firebaseProvider(CONFIG);

		await expect(provider.signInWithGoogle()).rejects.toMatchObject({
			name: 'AuthError',
			message: 'Your browser blocked the Google window. Allow pop-ups for this site and try again.'
		});
	});
});
