import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '#lib/api/client.ts';
import {
	canMakeTemplates,
	createTemplateDraft,
	draftForm,
	pdfUploads,
	templateProblem,
	templatesBlocked
} from '#lib/custom-templates.ts';
import { fakeApi, json } from '../extension/fake-api.ts';

const meter = (message: string | null) => ({ used: 1, limit: 1, message });

describe('draftForm', () => {
	it('sends the file, or the earlier upload, and never both', () => {
		const file = new File(['%PDF'], 'cv.pdf', { type: 'application/pdf' });
		const withFile = draftForm({ file });
		expect((withFile.get('file') as File).name).toBe('cv.pdf');
		expect(withFile.has('upload_id')).toBe(false);

		const again = draftForm({ uploadId: 'abc' });
		expect(again.get('upload_id')).toBe('abc');
		expect(again.has('file')).toBe(false);
	});
});

describe('createTemplateDraft', () => {
	afterEach(() => vi.unstubAllGlobals());

	it('posts multipart form data and returns the draft', async () => {
		let contentType = '';
		fakeApi({
			'POST /api/v1/templates/custom': (request) => {
				contentType = request.headers.get('content-type') ?? '';
				return json({ id: 'u-aaaaaaaaa2', name: 'Slate', status: 'draft' }, 201);
			}
		});

		const draft = await createTemplateDraft({ uploadId: 'abc' });

		expect(draft.id).toBe('u-aaaaaaaaa2');
		expect(contentType).toContain('multipart/form-data');
	});
});

describe('templateProblem', () => {
	it('keeps the limit message and marks it as a limit', () => {
		const error = new ApiError(402, 'quota_exceeded', 'You have 1 custom template.', {
			resource: 'templates'
		});
		expect(templateProblem(error)).toEqual({ message: 'You have 1 custom template.', limit: true });
	});

	it('shows the api message for a refused file, a failed template and a failed Claude call', () => {
		for (const [code, message] of [
			['validation_failed', 'This file is not a PDF. Upload a PDF file.'],
			['template_failed', 'We could not turn this CV into a template. Try a simpler PDF.'],
			['claude_unavailable', 'Drafting a template needs Claude, which is not set up yet.'],
			['provider_error', 'Claude could not finish this template. Wait a minute and try again.'],
			['provider_timeout', 'Claude could not finish this template. Wait a minute and try again.']
		] as const) {
			expect(templateProblem(new ApiError(422, code, message))).toEqual({ message, limit: false });
		}
	});

	it('falls back to a plain message for anything else', () => {
		expect(templateProblem(new Error('boom'))).toEqual({
			message: 'Something went wrong. Try again.',
			limit: false
		});
	});
});

describe('what the dialog may offer', () => {
	it('offers only PDFs from earlier uploads', () => {
		const rows = [
			{ id: '1', mime_type: 'application/pdf' },
			{
				id: '2',
				mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
			}
		];
		expect(pdfUploads(rows).map((row) => row.id)).toEqual(['1']);
	});

	it('needs a Claude model on the server', () => {
		expect(canMakeTemplates([{ provider: 'mimo' }, { provider: 'gemini' }])).toBe(false);
		expect(canMakeTemplates([{ provider: 'mimo' }, { provider: 'claude' }])).toBe(true);
		expect(canMakeTemplates([])).toBe(false);
	});

	it('is blocked by AI usage first, then by room for another template', () => {
		expect(templatesBlocked(null)).toBeNull();
		expect(templatesBlocked({ ai_runs: meter(null), templates: meter(null) })).toBeNull();
		expect(templatesBlocked({ ai_runs: meter('No AI usage.'), templates: meter('No room.') })).toBe(
			'No AI usage.'
		);
		expect(templatesBlocked({ ai_runs: meter(null), templates: meter('No room.') })).toBe(
			'No room.'
		);
	});
});
