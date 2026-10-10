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
	signOut(): Promise<void>;
}

/** Local development (AUTH_MODE=dev): always signed in as DEV_USER. */
export function devProvider(email = DEV_USER): AuthProvider {
	const unsupported = async () => {
		throw new AuthError('Sign-in is not used in local development.');
	};
	return {
		watch: (callback) => callback(email),
		headers: async () => ({ 'X-Dev-User': email }),
		signInWithGoogle: unsupported,
		sendEmailLink: unsupported,
		isEmailLink: () => false,
		completeEmailLink: unsupported,
		signOut: async () => {}
	};
}

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

/** Firebase Auth with Google and email-link sign-in. The SDK loads on first use. */
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
		signOut: () => mapErrors(() => firebaseAuth.signOut(auth))
	};
}
