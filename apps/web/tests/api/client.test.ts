import { describe, expect, it, vi } from 'vitest';
import {
	ApiError,
	createApi,
	DEV_USER,
	errorMessage,
	filenameFrom,
	toApiError,
	unwrap
} from '#lib/api/client.ts';

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('api client', () => {
	it('sends the dev user header and parses the response', async () => {
		const fetch = vi.fn(async (request: Request) => {
			expect(request.headers.get('X-Dev-User')).toBe(DEV_USER);
			expect(new URL(request.url).pathname).toBe('/api/v1/profiles');
			return json([]);
		});
		const api = createApi(fetch);

		await expect(unwrap(api.GET('/api/v1/profiles'))).resolves.toEqual([]);
		expect(fetch).toHaveBeenCalledOnce();
	});

	it('turns the error envelope into an ApiError', async () => {
		const envelope = {
			error: { code: 'not_found', message: 'This CV does not exist or was deleted.', details: {} }
		};
		const api = createApi(async () => json(envelope, 404));

		const error = await unwrap(
			api.GET('/api/v1/documents/{document_id}', { params: { path: { document_id: 'x' } } })
		).catch((e: unknown) => e);

		expect(error).toBeInstanceOf(ApiError);
		expect(error).toMatchObject({ status: 404, code: 'not_found' });
		expect(errorMessage(error)).toBe('This CV does not exist or was deleted.');
	});

	it('explains errors without an envelope', () => {
		const error = toApiError(new Response('oops', { status: 502 }), 'oops');
		expect(error.code).toBe('http_error');
		expect(error.message).toBe('Something went wrong on the server (status 502). Try again.');
	});

	it('reports network failures plainly', async () => {
		const api = createApi(async () => {
			throw new TypeError('Failed to fetch');
		});

		await expect(unwrap(api.GET('/api/v1/profiles'))).rejects.toMatchObject({
			code: 'network',
			message: 'Could not reach the server. Check your connection and try again.'
		});
	});

	it('lets aborts through untouched', async () => {
		const abort = new DOMException('Aborted', 'AbortError');
		await expect(unwrap(Promise.reject(abort))).rejects.toBe(abort);
	});

	it('has a generic message for unknown errors', () => {
		expect(errorMessage(new Error('x'))).toBe('Something went wrong. Try again.');
	});
});

describe('filenameFrom', () => {
	it.each([
		[`attachment; filename="Zoe-CV.pdf"; filename*=UTF-8''Zo%C3%AB-CV.pdf`, 'Zoë-CV.pdf'],
		['attachment; filename="Ama-CV.pdf"', 'Ama-CV.pdf'],
		[`attachment; filename*=UTF-8''%E0%A4%A`, 'CV.pdf'],
		[null, 'CV.pdf']
	])('reads %j', (header, expected) => {
		expect(filenameFrom(header, 'CV.pdf')).toBe(expected);
	});
});
