import { AuthError, DEV_USER, type Schemas } from '#lib/api/client.ts';

export type FirebaseConfig = Schemas['FirebaseConfig'];

/** The sign-in backend: Firebase in deployed environments, a fixed dev user locally. */
export interface AuthProvider {
	/** Calls back with the signed-in email (null when signed out), now and on every change. */
	watch(callback: (email: string | null) => void): void;
	headers(): Promise<Record<string, string>>;
	signInWithGoogle(): Promise<void>;
	sendEmailLink(email: string, continueUrl: string): Promise<void>;
	isEmailLink(url: string): boolean;
	completeEmailLink(email: string, url: string): Promise<void>;
	/** For accounts made with a password, such as the store review account; there is no sign-up. */
	signInWithPassword(email: string, password: string): Promise<void>;
	signOut(): Promise<void>;
}

const DEV_SIGNED_OUT_KEY = 'vitae.devSignedOut';

/** Whether the dev user signed out in this browser, so a reload keeps them signed out. */
const devSignedOut = {
	get(): boolean {
		try {
			return localStorage.getItem(DEV_SIGNED_OUT_KEY) === 'true';
		} catch {
			return false;
		}
	},
	set(signedOut: boolean): void {
		try {
			if (signedOut) localStorage.setItem(DEV_SIGNED_OUT_KEY, 'true');
			else localStorage.removeItem(DEV_SIGNED_OUT_KEY);
		} catch {
			// Without storage, signing out lasts until the page reloads.
		}
	}
};

/**
 * Local development (AUTH_MODE=dev): signed in as DEV_USER until they sign out, so the landing
 * and sign-in pages can be seen. "Continue with Google" signs back in as DEV_USER; no email is sent.
 */
export function devProvider(email = DEV_USER): AuthProvider {
	let signedIn = !devSignedOut.get();
	const watchers = new Set<(email: string | null) => void>();
	const current = () => (signedIn ? email : null);
	const change = (next: boolean) => {
		signedIn = next;
		devSignedOut.set(!next);
		for (const watcher of watchers) watcher(current());
	};
	const unsupported = async () => {
		throw new AuthError('Email links are not sent in local development. Use Continue with Google.');
	};
	const noPasswords = async () => {
		throw new AuthError('Passwords are not used in local development. Use Continue with Google.');
	};
	return {
		watch: (callback) => {
			watchers.add(callback);
			callback(current());
		},
		headers: async (): Promise<Record<string, string>> => (signedIn ? { 'X-Dev-User': email } : {}),
		signInWithGoogle: async () => change(true),
		sendEmailLink: unsupported,
		isEmailLink: () => false,
		completeEmailLink: unsupported,
		signInWithPassword: noPasswords,
		signOut: async () => change(false)
	};
}

// Firebase does not say which of the two was wrong, so neither do we.
const WRONG_PASSWORD = 'The email or password is wrong. Check both and try again.';

// Firebase error codes the user can do something about; anything else gets a generic message.
const FIREBASE_MESSAGES: Record<string, string> = {
	'auth/popup-closed-by-user': 'The Google window was closed before sign-in finished. Try again.',
	'auth/cancelled-popup-request':
		'The Google window was closed before sign-in finished. Try again.',
	'auth/popup-blocked':
		'Your browser blocked the Google window. Allow pop-ups for this site and try again.',
	'auth/invalid-email': 'Check the email address and try again.',
	'auth/invalid-action-code':
		'This sign-in link has expired or was already used. Request a new one.',
	'auth/expired-action-code':
		'This sign-in link has expired or was already used. Request a new one.',
	'auth/network-request-failed':
		'Could not reach the sign-in service. Check your connection and try again.',
	'auth/invalid-credential': WRONG_PASSWORD,
	'auth/invalid-login-credentials': WRONG_PASSWORD,
	'auth/wrong-password': WRONG_PASSWORD,
	'auth/user-not-found': WRONG_PASSWORD,
	'auth/too-many-requests': 'Too many attempts. Wait a few minutes and try again.',
	'auth/user-disabled': 'This account is disabled.'
};

export function authErrorFrom(error: unknown): AuthError {
	const code = (error as { code?: unknown } | null)?.code;
	const message = typeof code === 'string' ? FIREBASE_MESSAGES[code] : undefined;
	return new AuthError(message ?? 'Sign-in failed. Try again.');
}

async function mapErrors<T>(action: () => Promise<T>): Promise<T> {
	try {
		return await action();
	} catch (error) {
		throw authErrorFrom(error);
	}
}

/** Firebase Auth with Google, email-link and password sign-in. The SDK loads on first use. */
export async function firebaseProvider(config: FirebaseConfig): Promise<AuthProvider> {
	const [{ initializeApp }, firebaseAuth] = await Promise.all([
		import('firebase/app'),
		import('firebase/auth')
	]);
	const app = initializeApp({
		apiKey: config.api_key,
		authDomain: config.auth_domain,
		projectId: config.project_id,
		appId: config.app_id
	});
	const auth = firebaseAuth.getAuth(app);

	return {
		watch: (callback) =>
			firebaseAuth.onAuthStateChanged(auth, (user) => callback(user?.email ?? null)),
		async headers(): Promise<Record<string, string>> {
			const user = auth.currentUser;
			if (!user) return {};
			// Refreshes the token when it is close to expiry.
			return { Authorization: `Bearer ${await user.getIdToken()}` };
		},
		signInWithGoogle: () =>
			mapErrors(async () => {
				const provider = new firebaseAuth.GoogleAuthProvider();
				provider.setCustomParameters({ prompt: 'select_account' });
				await firebaseAuth.signInWithPopup(auth, provider);
			}),
		sendEmailLink: (email, continueUrl) =>
			mapErrors(() =>
				firebaseAuth.sendSignInLinkToEmail(auth, email, { url: continueUrl, handleCodeInApp: true })
			),
		isEmailLink: (url) => firebaseAuth.isSignInWithEmailLink(auth, url),
		completeEmailLink: (email, url) =>
			mapErrors(async () => {
				await firebaseAuth.signInWithEmailLink(auth, email, url);
			}),
		signInWithPassword: (email, password) =>
			mapErrors(async () => {
				await firebaseAuth.signInWithEmailAndPassword(auth, email, password);
			}),
		signOut: () => mapErrors(() => firebaseAuth.signOut(auth))
	};
}
