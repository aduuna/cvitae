import { vi } from 'vitest';
import type { AuthProvider } from '#lib/auth/provider.ts';

/** An AuthProvider whose sign-in state the test controls. */
export function fakeProvider(initial: string | null = null) {
	let listener: (email: string | null) => void = () => {};
	let email = initial;
	const emit = (next: string | null) => {
		email = next;
		listener(next);
	};
	const provider: AuthProvider = {
		watch: (callback) => {
			listener = callback;
			callback(email);
		},
		headers: vi.fn(async (): Promise<Record<string, string>> =>
			email ? { Authorization: `Bearer token-for-${email}` } : {}
		),
		signInWithGoogle: vi.fn(async () => emit('ada@example.com')),
		sendEmailLink: vi.fn(async () => {}),
		isEmailLink: vi.fn((url: string) => url.includes('oobCode=')),
		completeEmailLink: vi.fn(async (address: string) => emit(address)),
		signOut: vi.fn(async () => emit(null))
	};
	return { provider, emit };
}
