import { describe, expect, it, vi } from 'vitest';
import { importForm, recentUploads, runImport } from '#lib/ai/imports.ts';
import { modelLabel, modelOptions, otherModels, pickModel } from '#lib/ai/models.ts';
import type { AiModelInfo } from '#lib/cv/types.ts';

const MODELS: AiModelInfo[] = [
	{ id: 'mimo-flash', label: 'MiMo Flash', provider: 'mimo', plan: 'free' },
	{ id: 'claude-haiku', label: 'Claude Haiku', provider: 'claude', plan: 'free' },
	{ id: 'gemini-flash-lite', label: 'Gemini Flash-Lite', provider: 'gemini', plan: 'free' },
	{ id: 'mimo-pro', label: 'MiMo Pro', provider: 'mimo', plan: 'pro' },
	{ id: 'gemini-flash', label: 'Gemini Flash', provider: 'gemini', plan: 'pro' },
	{ id: 'claude-sonnet', label: 'Claude Sonnet', provider: 'claude', plan: 'pro' }
];

describe('models', () => {
	it('marks Pro models and disables them only when plans are enforced for Free users', () => {
		expect(modelOptions(MODELS).filter((o) => o.disabled)).toEqual([]);
		expect(modelOptions(MODELS, { plan: 'pro', enforced: true }).filter((o) => o.disabled)).toEqual(
			[]
		);
		const free = modelOptions(MODELS, { plan: 'free', enforced: true });
		expect(free.filter((o) => o.disabled).map((o) => o.label)).toEqual([
			'MiMo Pro (Pro)',
			'Gemini Flash (Pro)',
			'Claude Sonnet (Pro)'
		]);
	});

	it('picks the preference, else the default, else the first offered', () => {
		expect(pickModel('claude-haiku', MODELS, 'mimo-flash')).toBe('claude-haiku');
		expect(pickModel(null, MODELS, 'mimo-flash')).toBe('mimo-flash');
		expect(pickModel('claude-sonnet', MODELS.slice(0, 2), 'gemini-flash')).toBe('mimo-flash');
		expect(pickModel(null, [], 'mimo-flash')).toBeNull();
	});

	it('labels models and lists the others', () => {
		expect(modelLabel('gemini-flash-lite', MODELS)).toBe('Gemini Flash-Lite');
		expect(modelLabel('mimo-pro', [])).toBe('mimo-pro');
		expect(otherModels('mimo-flash', MODELS).map((m) => m.id)).not.toContain('mimo-flash');
		expect(otherModels('mimo-flash', MODELS)).toHaveLength(5);
	});
});

describe('imports', () => {
	it('builds the multipart form for each source', () => {
		const file = new File(['%PDF-1.7'], 'cv.pdf', { type: 'application/pdf' });

		const fromFile = importForm({ file }, 'mimo-flash');
		const fromText = importForm({ text: 'My CV' }, 'claude-haiku');
		const fromUpload = importForm({ uploadId: 'u1' }, 'mimo-flash');

		expect((fromFile.get('file') as File).name).toBe('cv.pdf');
		expect(fromFile.get('ai_model')).toBe('mimo-flash');
		expect([fromText.get('text'), fromText.get('ai_model')]).toEqual(['My CV', 'claude-haiku']);
		expect(fromUpload.get('upload_id')).toBe('u1');
		expect(fromUpload.get('file')).toBeNull();
	});

	it('lists the newest distinct uploads, once each', () => {
		const upload = (id: string, filename: string, size_bytes = 100) => ({
			id,
			filename,
			size_bytes,
			mime_type: 'application/pdf',
			created_at: '2026-10-17T12:00:00Z'
		});
		const uploads = [
			upload('5', 'cv.pdf'),
			upload('4', 'cv.pdf'),
			upload('3', 'cv.pdf', 200),
			upload('2', 'old.pdf'),
			upload('1', 'older.pdf')
		];

		expect(recentUploads(uploads).map((u) => u.id)).toEqual(['5', '3', '2']);
		expect(recentUploads(uploads, 10).map((u) => u.id)).toEqual(['5', '3', '2', '1']);
	});

	it('posts the form without a JSON content type', async () => {
		const fetch = vi.fn(async (request: Request) => {
			expect(new URL(request.url).pathname).toBe('/api/v1/imports');
			expect(request.headers.get('Content-Type')).toMatch(/^multipart\/form-data; boundary=/);
			const form = await request.formData();
			expect(form.get('text')).toBe('My CV');
			return new Response(
				JSON.stringify({
					upload_id: null,
					draft: {},
					ai_model: 'mimo-flash',
					provider: 'mimo',
					model: 'm'
				}),
				{ headers: { 'Content-Type': 'application/json' } }
			);
		});
		vi.stubGlobal('fetch', fetch);

		const result = await runImport({ text: 'My CV' }, 'mimo-flash');

		expect(result.ai_model).toBe('mimo-flash');
		expect(fetch).toHaveBeenCalledOnce();
		vi.unstubAllGlobals();
	});
});
