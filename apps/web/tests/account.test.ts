import { afterEach, describe, expect, it, vi } from 'vitest';
import { deleteAccount, exportAccount } from '#lib/account.ts';
import { ApiError, DEV_USER } from '#lib/api/client.ts';

function stubFetch(respond: (request: Request) => Response) {
	const calls: Request[] = [];
	vi.stubGlobal(
		'fetch',
		vi.fn(async (request: Request) => {
			calls.push(request);
			return respond(request);
		})
	);
	return calls;
}

/** What the download link was told to save, in place of a real download. */
function captureDownload() {
	const saved: { name: string; blob: Blob }[] = [];
	let blob: Blob | undefined;
	URL.createObjectURL = vi.fn((object: Blob | MediaSource) => {
		blob = object as Blob;
		return 'blob:export';
	});
	URL.revokeObjectURL = vi.fn();
	vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
		this: HTMLAnchorElement
	) {
		saved.push({ name: this.download, blob: blob as Blob });
	});
	return saved;
}

const envelope = (code: string, message: string) =>
	JSON.stringify({ error: { code, message, details: {} } });

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe('exportAccount', () => {
	it('downloads the export as a file, named as the api names it', async () => {
		const saved = captureDownload();
		const calls = stubFetch(
			() =>
				new Response('{"account":{"email":"ada@example.com"}}', {
					headers: {
						'content-type': 'application/json',
						'content-disposition': 'attachment; filename="chameleon-vitae-export.json"'
					}
				})
		);

		await exportAccount();

		expect(calls).toHaveLength(1);
		expect(calls[0]!.method).toBe('GET');
		expect(new URL(calls[0]!.url).pathname).toBe('/api/v1/me/export');
		expect(calls[0]!.headers.get('X-Dev-User')).toBe(DEV_USER);
		expect(saved.map((file) => file.name)).toEqual(['chameleon-vitae-export.json']);
		expect(await saved[0]!.blob.text()).toBe('{"account":{"email":"ada@example.com"}}');
	});

	it('falls back to a name of its own', async () => {
		const saved = captureDownload();
		stubFetch(() => new Response('{}', { headers: { 'content-type': 'application/json' } }));

		await exportAccount();

		expect(saved.map((file) => file.name)).toEqual(['chameleon-vitae-export.json']);
	});

	it('throws the api error and saves nothing when the export fails', async () => {
		const saved = captureDownload();
		stubFetch(
			() =>
				new Response(envelope('unauthorized', 'Your session has expired. Sign in again.'), {
					status: 401,
					headers: { 'content-type': 'application/json' }
				})
		);

		await expect(exportAccount()).rejects.toMatchObject({
			status: 401,
			message: 'Your session has expired. Sign in again.'
		});
		expect(saved).toEqual([]);
	});

	it('reports a network failure plainly', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new TypeError('Failed to fetch');
			})
		);

		await expect(exportAccount()).rejects.toMatchObject({ code: 'network' });
	});
});

describe('deleteAccount', () => {
	it('sends the typed email in the body of a DELETE', async () => {
		const calls = stubFetch(() => new Response(null, { status: 204 }));

		await expect(deleteAccount('ada@example.com')).resolves.toBeUndefined();

		expect(calls).toHaveLength(1);
		expect(calls[0]!.method).toBe('DELETE');
		expect(new URL(calls[0]!.url).pathname).toBe('/api/v1/me');
		expect(await calls[0]!.json()).toEqual({ email: 'ada@example.com' });
	});

	it('throws the api error when the account is not deleted', async () => {
		stubFetch(
			() =>
				new Response(
					envelope('conflict', 'Cancel your Pro subscription first: use Manage subscription.'),
					{ status: 409, headers: { 'content-type': 'application/json' } }
				)
		);

		const error = await deleteAccount('ada@example.com').catch((e: unknown) => e);

		expect(error).toBeInstanceOf(ApiError);
		expect(error).toMatchObject({ status: 409, code: 'conflict' });
	});
});
