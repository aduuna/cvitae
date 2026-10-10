import createClient, { type Middleware } from 'openapi-fetch';
import type { components, paths } from './schema';

export type Schemas = components['schemas'];

/** Until Firebase sign-in (M2), the api runs with AUTH_MODE=dev and trusts this header. */
export const DEV_USER: string = import.meta.env.VITE_DEV_USER ?? 'dev@localhost';

/** An error response in the api's envelope, or a request that never got an answer. */
export class ApiError extends Error {
	constructor(
		readonly status: number,
		readonly code: string,
		message: string,
		readonly details: Record<string, unknown> = {}
	) {
		super(message);
		this.name = 'ApiError';
	}
}

const devAuth: Middleware = {
	onRequest({ request }) {
		request.headers.set('X-Dev-User', DEV_USER);
		return request;
	}
};

export function createApi(fetchImpl: (request: Request) => Promise<Response> = (r) => fetch(r)) {
	const client = createClient<paths>({
		baseUrl: globalThis.location?.origin ?? '',
		fetch: fetchImpl
	});
	client.use(devAuth);
	return client;
}

export const api = createApi();

function isEnvelope(value: unknown): value is Schemas['ErrorEnvelope'] {
	const error = (value as { error?: { code?: unknown } } | null)?.error;
	return typeof error?.code === 'string';
}

export function toApiError(response: Response, body: unknown): ApiError {
	if (isEnvelope(body)) {
		const { code, message, details } = body.error;
		return new ApiError(response.status, code, message, details ?? {});
	}
	return new ApiError(
		response.status,
		'http_error',
		`Something went wrong on the server (status ${response.status}). Try again.`
	);
}

interface FetchResult<T> {
	data?: T;
	error?: unknown;
	response: Response;
}

/** The response data, or an ApiError. Aborted requests reject with their AbortError. */
export async function unwrap<T>(request: Promise<FetchResult<T>>): Promise<T> {
	let result: FetchResult<T>;
	try {
		result = await request;
	} catch (error) {
		if (error instanceof DOMException && error.name === 'AbortError') throw error;
		throw new ApiError(
			0,
			'network',
			'Could not reach the server. Check your connection and try again.'
		);
	}
	if (!result.response.ok) throw toApiError(result.response, result.error);
	return result.data as T;
}

/** A user-facing message for any error thrown by an api call. */
export function errorMessage(error: unknown): string {
	if (error instanceof ApiError) return error.message;
	return 'Something went wrong. Try again.';
}

/** The file name from a Content-Disposition header, preferring the UTF-8 form. */
export function filenameFrom(header: string | null, fallback: string): string {
	if (!header) return fallback;
	const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header);
	if (encoded?.[1]) {
		try {
			return decodeURIComponent(encoded[1]);
		} catch {
			// Fall through to the plain name.
		}
	}
	const plain = /filename="([^"]+)"/i.exec(header);
	return plain?.[1] ?? fallback;
}

/** Save a blob as a file through a temporary link. */
export function saveFile(blob: Blob, filename: string): void {
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = filename;
	document.body.append(link);
	link.click();
	link.remove();
	setTimeout(() => URL.revokeObjectURL(url), 0);
}
