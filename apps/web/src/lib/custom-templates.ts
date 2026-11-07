import { api, ApiError, errorMessage, unwrap } from '#lib/api/client.ts';
import { limitReached, type Usage } from '#lib/billing/plans.ts';
import type { CustomTemplate, CustomTemplateDraft, CustomTemplateSource } from '#lib/cv/types.ts';

/** A PDF to copy the look of: a file to upload, or an earlier upload. */
export type TemplateSourceInput = { file: File } | { uploadId: string };

export const NAME_MAX = 60;

export function draftForm(source: TemplateSourceInput): FormData {
	const form = new FormData();
	if ('file' in source) form.append('file', source.file, source.file.name);
	else form.append('upload_id', source.uploadId);
	return form;
}

/**
 * POST /templates/custom as multipart form data. The request waits for the whole generation, up to
 * about two minutes, so callers show progress and pass a signal to cancel.
 */
export function createTemplateDraft(
	source: TemplateSourceInput,
	signal?: AbortSignal
): Promise<CustomTemplateDraft> {
	const form = draftForm(source);
	return unwrap(
		api.POST('/api/v1/templates/custom', { body: {}, bodySerializer: () => form, signal })
	);
}

/** Make a draft usable, under the name the user chose. */
export function confirmTemplate(id: string, name: string): Promise<CustomTemplate> {
	return unwrap(
		api.PATCH('/api/v1/templates/custom/{template_id}', {
			params: { path: { template_id: id } },
			body: { name, status: 'ready' }
		})
	);
}

export function renameTemplate(id: string, name: string): Promise<CustomTemplate> {
	return unwrap(
		api.PATCH('/api/v1/templates/custom/{template_id}', {
			params: { path: { template_id: id } },
			body: { name }
		})
	);
}

/** Delete a template, or discard a draft. */
export async function deleteTemplate(id: string): Promise<void> {
	await unwrap(
		api.DELETE('/api/v1/templates/custom/{template_id}', {
			params: { path: { template_id: id } }
		})
	);
}

export function loadTemplateSource(id: string): Promise<CustomTemplateSource> {
	return unwrap(
		api.GET('/api/v1/templates/custom/{template_id}/source', {
			params: { path: { template_id: id } }
		})
	);
}

/** One page of a template rendered with the user's profile, drafts included. */
export async function loadTemplatePreview(id: string): Promise<string | null> {
	const pages = await unwrap(
		api.GET('/api/v1/templates/{template_id}/preview', {
			params: { path: { template_id: id } }
		})
	);
	return pages.pages[0] ?? null;
}

/** What went wrong when making a template, in words for the dialog. */
export interface TemplateProblem {
	message: string;
	/** A plan limit (AI usage or room for another template): shown with the way to Pro. */
	limit: boolean;
}

/**
 * Turns an error from making or saving a template into its message. The api words most of them
 * (a DOCX, an unreadable file, a template that could not be made to render, no Claude key, a limit);
 * a failed or slow Claude call is reworded because its message offers another model, and a
 * template always runs on Claude.
 */
export function templateProblem(error: unknown): TemplateProblem {
	if (error instanceof ApiError) {
		if (error.status === 402 && error.code === 'quota_exceeded') {
			return { message: error.message, limit: true };
		}
		if (error.code === 'provider_error' || error.code === 'provider_timeout') {
			return {
				message:
					'Claude could not finish this template. Wait a minute and try again, or try a PDF with a simpler layout.',
				limit: false
			};
		}
	}
	return { message: errorMessage(error), limit: false };
}

/** Earlier uploads that can be copied: PDFs only, as a DOCX does not keep how a CV looks. */
export function pdfUploads<T extends { mime_type: string }>(uploads: T[]): T[] {
	return uploads.filter((upload) => upload.mime_type === 'application/pdf');
}

/** Whether the server can make templates: they always run on Claude, so a Claude model must be on. */
export function canMakeTemplates(models: { provider: string }[]): boolean {
	return models.some((model) => model.provider === 'claude');
}

/** Why no template can be made now: the AI usage or the room for another template, or null. */
export function templatesBlocked(
	usage: Pick<Usage, 'ai_runs' | 'templates'> | null
): string | null {
	return limitReached(usage?.ai_runs, usage?.templates);
}
