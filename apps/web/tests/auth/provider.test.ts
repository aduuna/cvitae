import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthError, DEV_USER } from '#lib/api/client.ts';
import { authErrorFrom, devProvider, firebaseProvider } from '#lib/auth/provider.ts';

const firebase = vi.hoisted(() => ({
	user: null as { email: string | null; getIdToken: () => Promise<string> } | null,
	listener: null as ((user: unknown) => void) | null,
	initializeApp: vi.fn(() => ({ name: 'app' })),
	signInWithPopup: vi.fn(async () => {}),
	sendSignInLinkToEmail: vi.fn(async () => {}),
	signInWithEmailLink: vi.fn(async () => {}),
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
		signOut: firebase.signOut
	};
});

const CONFIG = { api_key: 'key', auth_domain: 'p.firebaseapp.com', project_id: 'p', app_id: 'a' };

describe('devProvider', () => {
	it('is always signed in as the dev user', async () => {
		const provider = devProvider();
		const seen: (string | null)[] = [];

		provider.watch((email) => seen.push(email));

		expect(seen).toEqual([DEV_USER]);
		expect(await provider.headers()).toEqual({ 'X-Dev-User': DEV_USER });
		expect(provider.isEmailLink('http://x/?oobCode=1')).toBe(false);
		await expect(provider.signOut()).resolves.toBeUndefined();
		await expect(provider.signInWithGoogle()).rejects.toBeInstanceOf(AuthError);
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

	it('turns Firebase errors into messages', async () => {
		firebase.signInWithPopup.mockRejectedValueOnce({ code: 'auth/popup-blocked' });
		const provider = await firebaseProvider(CONFIG);

		await expect(provider.signInWithGoogle()).rejects.toMatchObject({
			name: 'AuthError',
			message: 'Your browser blocked the Google window. Allow pop-ups for this site and try again.'
		});
	});
});
