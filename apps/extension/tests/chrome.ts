import { vi } from 'vitest';

type Listener = (...args: never[]) => unknown;

function event() {
	const listeners = new Set<Listener>();
	return {
		addListener: (listener: Listener) => void listeners.add(listener),
		removeListener: (listener: Listener) => void listeners.delete(listener),
		emit: (...args: unknown[]) =>
			[...listeners].map((listener) => (listener as (...a: unknown[]) => unknown)(...args))
	};
}

export interface FakeTab {
	id: number;
	url?: string;
	windowId?: number;
}

/**
 * The parts of the `chrome` namespace the extension uses, in memory. Storage behaves like the
 * real one; the rest are spies a test can program.
 */
export function fakeChrome(tab: FakeTab | null = { id: 1, url: 'https://jobs.example.com/apply' }) {
	const store: Record<string, unknown> = {};
	const changed = event();
	const keysOf = (keys: string | string[] | null | undefined) =>
		keys == null ? Object.keys(store) : typeof keys === 'string' ? [keys] : keys;
	const chrome = {
		runtime: {
			id: 'cvitae-test',
			sendMessage: vi.fn<(message: unknown) => Promise<unknown>>(async () => undefined),
			onMessage: event(),
			onInstalled: event()
		},
		storage: {
			local: {
				get: async (keys?: string | string[] | null) =>
					Object.fromEntries(
						keysOf(keys)
							.filter((k) => k in store)
							.map((k) => [k, store[k]])
					),
				set: async (items: Record<string, unknown>) => {
					Object.assign(store, structuredClone(items));
					changed.emit(items, 'local');
				},
				remove: async (keys: string | string[]) => {
					for (const key of keysOf(keys)) delete store[key];
					changed.emit({}, 'local');
				}
			},
			onChanged: changed
		},
		tabs: {
			query: vi.fn(async () => (tab ? [tab] : [])),
			create: vi.fn(async (props: { url: string }) => ({ id: 99, ...props })),
			onActivated: event(),
			onUpdated: event()
		},
		scripting: {
			executeScript: vi.fn<(injection: unknown) => Promise<unknown[]>>(async () => []),
			registerContentScripts: vi.fn(async () => {})
		},
		permissions: {
			request: vi.fn(async () => true),
			contains: vi.fn(async () => false)
		},
		action: { onClicked: event() },
		sidePanel: { open: vi.fn(async () => {}) }
	};
	return { chrome, store, tab };
}

export type FakeChrome = ReturnType<typeof fakeChrome>;

/** Install a fake as the global `chrome` for the current test. */
export function installChrome(tab?: FakeTab | null): FakeChrome {
	const fake = fakeChrome(tab);
	vi.stubGlobal('chrome', fake.chrome);
	return fake;
}
