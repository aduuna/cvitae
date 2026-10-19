// @vitest-environment-options { "url": "http://localhost:5173/app/extension" }
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ExtensionMessage, PageMessage } from '@web/extension/protocol.ts';
import { installChrome, type FakeChrome } from './chrome.ts';

let fake: FakeChrome;
const answers: ExtensionMessage[] = [];

/** As the page posts a message: from this window, on the app's origin. */
function fromPage(data: PageMessage, origin = 'http://localhost:5173') {
	window.dispatchEvent(new MessageEvent('message', { data, origin, source: window }));
}

beforeAll(async () => {
	fake = installChrome();
	fake.chrome.runtime.sendMessage.mockImplementation(async (message: unknown) => {
		const { type, token } = message as { type: string; token?: string };
		if (type === 'connection') return { connectedAs: null };
		return token === 'cvx_good'
			? { ok: true, email: 'ada@example.com' }
			: { ok: false, message: 'The server did not accept this connection.' };
	});
	window.addEventListener('message', (event) => {
		const data = event.data as ExtensionMessage;
		if (data?.source === 'cvitae-extension') answers.push(data);
	});
	await import('../src/connect.ts');
});

// The setup removes stubbed globals after each test; the script keeps using the same fake.
beforeEach(() => vi.stubGlobal('chrome', fake.chrome));

describe('the connect page script', () => {
	it('announces itself when it loads, and answers a ping', async () => {
		await vi.waitFor(() => expect(answers).toHaveLength(1));
		fromPage({ source: 'cvitae-app', type: 'ping' });

		await vi.waitFor(() => expect(answers).toHaveLength(2));
		expect(answers[1]).toEqual({ source: 'cvitae-extension', type: 'ready', connectedAs: null });
	});

	it('passes the token on and reports the outcome', async () => {
		answers.length = 0;
		fromPage({ source: 'cvitae-app', type: 'token', token: 'cvx_good', email: 'ada@example.com' });
		fromPage({ source: 'cvitae-app', type: 'token', token: 'cvx_bad', email: 'ada@example.com' });

		await vi.waitFor(() => expect(answers).toHaveLength(2));
		expect(answers).toContainEqual({
			source: 'cvitae-extension',
			type: 'connected',
			email: 'ada@example.com'
		});
		expect(answers).toContainEqual({
			source: 'cvitae-extension',
			type: 'failed',
			message: 'The server did not accept this connection.'
		});
		expect(fake.chrome.runtime.sendMessage).toHaveBeenCalledWith({
			type: 'connect',
			token: 'cvx_good',
			email: 'ada@example.com'
		});
	});

	it('ignores messages from another origin', async () => {
		fake.chrome.runtime.sendMessage.mockClear();

		fromPage(
			{ source: 'cvitae-app', type: 'token', token: 'cvx_good', email: 'x' },
			'https://evil.example'
		);
		await new Promise((resolve) => setTimeout(resolve, 20));

		expect(fake.chrome.runtime.sendMessage).not.toHaveBeenCalled();
	});
});
