import { api, unwrap } from '#lib/api/client.ts';
import type { AiModel, ImportResult, UploadSummary } from '#lib/cv/types.ts';

/** Exactly one of a file, pasted text or an earlier upload. */
export type ImportSource = { file: File } | { text: string } | { uploadId: string };

export function importForm(source: ImportSource, model: AiModel): FormData {
	const form = new FormData();
	if ('file' in source) form.append('file', source.file, source.file.name);
	else if ('text' in source) form.append('text', source.text);
	else form.append('upload_id', source.uploadId);
	form.append('ai_model', model);
	return form;
}

/**
 * The newest distinct files, for the short list of earlier uploads: uploading the same file again
 * (same name and size) keeps both, but the list shows it once. `uploads` is newest first.
 */
export function recentUploads(uploads: UploadSummary[], limit = 3): UploadSummary[] {
	const seen = new Set<string>();
	return uploads
		.filter((upload) => {
			const key = `${upload.filename}\u0000${upload.size_bytes}`;
			if (seen.has(key)) return false;
			seen.add(key);
			return true;
		})
		.slice(0, limit);
}

/** POST /imports as multipart form data; the browser sets the boundary. */
export function runImport(
	source: ImportSource,
	model: AiModel,
	signal?: AbortSignal
): Promise<ImportResult> {
	const form = importForm(source, model);
	return unwrap(api.POST('/api/v1/imports', { body: {}, bodySerializer: () => form, signal }));
}
