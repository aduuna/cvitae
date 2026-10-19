import createClient from 'openapi-fetch';
import { ApiError, filenameFrom, toApiError, unwrap, type Schemas } from '@web/api/client.ts';
import type { paths } from '@web/api/schema';
import { APP_URL } from '../config.ts';
import type { ApplicationData, JobDraft } from '../content/types.ts';
import type { SourceRef } from './settings.ts';

export type ExtensionSession = Schemas['ExtensionSession'];
export type SavedJob = Schemas['SavedJob'];

/** The api, called with the extension's token (only the /extension routes accept it). */
export function connectApi(token: string, fetchImpl: typeof fetch = (r) => fetch(r)) {
	const client = createClient<paths>({ baseUrl: APP_URL, fetch: fetchImpl });
	client.use({
		onRequest({ request }) {
			request.headers.set('Authorization', `Bearer ${token}`);
			return request;
		}
	});
	return client;
}

export type Api = ReturnType<typeof connectApi>;

/** The api turned the token down: the user disconnected this browser, or deleted the account. */
export function isRevoked(error: unknown): boolean {
	return error instanceof ApiError && error.status === 401;
}

export function loadSession(api: Api): Promise<ExtensionSession> {
	return unwrap(api.GET('/api/v1/extension/session'));
}

export function loadApplication(api: Api, source: SourceRef): Promise<ApplicationData> {
	return source.kind === 'profile'
		? unwrap(
				api.GET('/api/v1/extension/profiles/{profile_id}/application', {
					params: { path: { profile_id: source.id } }
				})
			)
		: unwrap(
				api.GET('/api/v1/extension/documents/{document_id}/application', {
					params: { path: { document_id: source.id } }
				})
			);
}

export interface CvFile {
	name: string;
	type: string;
	base64: string;
}

export type CvPdf = { ok: true; file: CvFile } | { ok: false; placeholders: number };

/** Bytes as base64, the form scripting.executeScript can pass to a page. */
export function toBase64(bytes: Uint8Array): string {
	let binary = '';
	for (let i = 0; i < bytes.length; i += 0x8000) {
		binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
	}
	return btoa(binary);
}

/** The CV as a PDF, or how many placeholders stop it from being exported. */
export async function loadCvPdf(api: Api, documentId: string): Promise<CvPdf> {
	const { data, error, response } = await api.GET(
		'/api/v1/extension/documents/{document_id}/cv.pdf',
		{
			params: { path: { document_id: documentId } },
			parseAs: 'arrayBuffer'
		}
	);
	if (response.status === 409) {
		const details = (error as { error?: { details?: { placeholders?: unknown[] } } } | undefined)
			?.error?.details;
		return { ok: false, placeholders: details?.placeholders?.length ?? 1 };
	}
	if (!response.ok || !(data instanceof ArrayBuffer)) throw toApiError(response, error);
	return {
		ok: true,
		file: {
			name: filenameFrom(response.headers.get('content-disposition'), 'CV.pdf'),
			type: 'application/pdf',
			base64: toBase64(new Uint8Array(data))
		}
	};
}

export function saveJob(api: Api, job: JobDraft): Promise<SavedJob> {
	return unwrap(
		api.POST('/api/v1/extension/jobs', {
			body: {
				description: job.description,
				title: job.title,
				company: job.company,
				url: job.url || null
			}
		})
	);
}

/** Revoke this browser's token. */
export async function disconnect(api: Api): Promise<void> {
	await unwrap(api.DELETE('/api/v1/extension/session'));
}
