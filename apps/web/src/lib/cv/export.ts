import { api, filenameFrom, saveFile, toApiError } from '#lib/api/client.ts';
import type { PlaceholderRef } from './types.ts';

export type ExportResult = { ok: true } | { ok: false; placeholders: PlaceholderRef[] };

/**
 * Download a CV as a PDF. Resolves with the remaining placeholders when the api refuses because
 * of them (unless `force`); throws an ApiError for anything else.
 */
export async function exportPdf(documentId: string, force = false): Promise<ExportResult> {
	const { data, error, response } = await api.GET('/api/v1/documents/{document_id}/export.pdf', {
		params: { path: { document_id: documentId }, query: { force } },
		parseAs: 'blob'
	});
	if (response.status === 409) {
		const details = (error as { error?: { details?: { placeholders?: PlaceholderRef[] } } })?.error
			?.details;
		return { ok: false, placeholders: details?.placeholders ?? [] };
	}
	if (!response.ok || !(data instanceof Blob)) throw toApiError(response, error);
	saveFile(data, filenameFrom(response.headers.get('content-disposition'), 'CV.pdf'));
	return { ok: true };
}
