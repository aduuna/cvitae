import { api, unwrap } from '#lib/api/client.ts';
import type { AiModel, ImportResult } from '#lib/cv/types.ts';

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

/** POST /imports as multipart form data; the browser sets the boundary. */
export function runImport(
	source: ImportSource,
	model: AiModel,
	signal?: AbortSignal
): Promise<ImportResult> {
	const form = importForm(source, model);
	return unwrap(api.POST('/api/v1/imports', { body: {}, bodySerializer: () => form, signal }));
}
