import { vi } from 'vitest';

/** A stand-in for the session singleton, for components that import it. */
export function sessionMock() {
	return {
		status: 'signed-out' as 'loading' | 'signed-out' | 'signed-in',
		email: null as string | null,
		me: null as { plan: string; email: string; display_name: string | null } | null,
		usage: null as Record<string, unknown> | null,
		plans: [] as unknown[],
		billingEnabled: false,
		signInWithGoogle: vi.fn(async () => {}),
		sendEmailLink: vi.fn(async () => {}),
		isEmailLink: vi.fn(() => true),
		completeEmailLink: vi.fn(async () => {}),
		signInWithPassword: vi.fn(async () => {}),
		signOut: vi.fn(async () => {}),
		loadMe: vi.fn(async () => ({})),
		refreshMe: vi.fn(async () => ({})),
		loadUsage: vi.fn(async () => ({})),
		refreshUsage: vi.fn(async () => ({})),
		updateMe: vi.fn(async () => ({}))
	};
}
