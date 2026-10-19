import { afterEach, describe, expect, it } from 'vitest';
import { browserLabel, findExtension, handOver } from '#lib/extension/connect.ts';
import { isExtensionMessage, isPageMessage } from '#lib/extension/protocol.ts';
import { fakeExtension, ready } from './fake-extension.ts';

const UA = {
	chromeMac:
		'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
	firefoxWindows:
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
	edgeWindows:
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
	firefoxLinux: 'Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0',
	chromeOs:
		'Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
};

describe('browserLabel', () => {
	it.each([
		[UA.chromeMac, 'Chrome on macOS'],
		[UA.firefoxWindows, 'Firefox on Windows'],
		[UA.edgeWindows, 'Edge on Windows'],
		[UA.firefoxLinux, 'Firefox on Linux'],
		[UA.chromeOs, 'Chrome on ChromeOS'],
		['', 'Browser']
	])('names %s', (userAgent, label) => {
		expect(browserLabel(userAgent)).toBe(label);
	});
});

describe('protocol', () => {
	it('accepts only well-formed messages from the other side', () => {
		expect(isPageMessage({ source: 'cvitae-app', type: 'ping' })).toBe(true);
		expect(isPageMessage({ source: 'cvitae-app', type: 'token', token: 't', email: 'e' })).toBe(
			true
		);
		expect(isPageMessage({ source: 'cvitae-app', type: 'token', token: 1, email: 'e' })).toBe(
			false
		);
		expect(isPageMessage({ source: 'cvitae-extension', type: 'ping' })).toBe(false);
		expect(isPageMessage('ping')).toBe(false);
		expect(isExtensionMessage(ready('ada@example.com'))).toBe(true);
		expect(isExtensionMessage({ source: 'cvitae-extension', type: 'ready' })).toBe(false);
		expect(isExtensionMessage({ source: 'cvitae-extension', type: 'connected', email: 'e' })).toBe(
			true
		);
		expect(isExtensionMessage({ source: 'cvitae-extension', type: 'failed', message: 'm' })).toBe(
			true
		);
		expect(isExtensionMessage({ source: 'cvitae-extension', type: 'other' })).toBe(false);
		expect(isExtensionMessage(null)).toBe(false);
	});
});

describe('findExtension', () => {
	let extension: ReturnType<typeof fakeExtension> | null = null;
	afterEach(() => extension?.remove());

	it('finds a running extension and the account it is connected to', async () => {
		extension = fakeExtension((message) =>
			message.type === 'ping' ? ready('ada@example.com') : null
		);

		expect(await findExtension(window, 500)).toEqual({ connectedAs: 'ada@example.com' });
		expect(extension.received).toEqual([{ source: 'cvitae-app', type: 'ping' }]);
	});

	it('gives up when nothing answers', async () => {
		expect(await findExtension(window, 20)).toBeNull();
	});

	it('ignores answers from another origin or window', async () => {
		const answer = (init: MessageEventInit) =>
			window.dispatchEvent(
				new MessageEvent('message', { data: ready('eve@example.com'), ...init })
			);
		const finding = findExtension(window, 50);
		answer({ origin: 'https://evil.example', source: window });
		answer({ origin: window.location.origin, source: null });

		expect(await finding).toBeNull();
	});
});

describe('handOver', () => {
	let extension: ReturnType<typeof fakeExtension> | null = null;
	afterEach(() => extension?.remove());

	it('hands the token over and waits for the extension to confirm', async () => {
		extension = fakeExtension((message) =>
			message.type === 'token'
				? { source: 'cvitae-extension', type: 'connected', email: message.email }
				: null
		);

		const result = await handOver('cvx_secret', 'ada@example.com', window, 500);

		expect(result).toEqual({ ok: true, email: 'ada@example.com' });
		expect(extension.received).toEqual([
			{ source: 'cvitae-app', type: 'token', token: 'cvx_secret', email: 'ada@example.com' }
		]);
	});

	it('passes on the reason the extension refused', async () => {
		extension = fakeExtension(() => ({
			source: 'cvitae-extension',
			type: 'failed',
			message: 'This token is not valid.'
		}));

		expect(await handOver('cvx_bad', 'ada@example.com', window, 500)).toEqual({
			ok: false,
			message: 'This token is not valid.'
		});
	});

	it('says so when the extension does not answer', async () => {
		const result = await handOver('cvx_secret', 'ada@example.com', window, 20);

		expect(result.ok).toBe(false);
		expect(!result.ok && result.message).toMatch(/did not answer/);
	});
});
