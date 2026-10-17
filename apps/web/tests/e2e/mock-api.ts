import { test as base, type Page, type Route } from '@playwright/test';
import type { Schemas } from '../../src/lib/api/client.ts';
import type {
	BulletDiff,
	CvContent,
	CvDocument,
	Job,
	Profile,
	AiModel,
	TailorResult,
	TemplateMeta,
	UploadSummary,
	Version
} from '../../src/lib/cv/types.ts';

/**
 * An in-memory stand-in for the api, installed with page.route. It keeps state across reloads
 * within a test and follows the real endpoints closely enough for the editor flows.
 */
export interface MockApi {
	me: Me;
	/** Pro models need Pro, as on the real server. */
	plansEnforced: boolean;
	billingEnabled: boolean;
	/** AI runs used this month. */
	aiRuns: number;
	subscription: Schemas['SubscriptionInfo'] | null;
	/** Checkouts started; verifying the last one upgrades to Pro. */
	checkouts: number;
	uploads: UploadSummary[];
	jobs: Job[];
	/** Provider of every AI call, in order. */
	aiCalls: { task: 'import' | 'tailor'; model: AiModel }[];
	profiles: Profile[];
	documents: CvDocument[];
	versions: Map<string, (Version & { content: CvContent })[]>;
	previewCalls: number;
}

type Me = Schemas['Me'];

const PLANS: Schemas['PlanInfo'][] = [
	{ id: 'free', label: 'Free', documents: 4, profiles: 2, ai_runs: 20 },
	{ id: 'pro', label: 'Pro', documents: 100, profiles: 10, ai_runs: 150 }
];

function limits(plan: Me['plan']): Schemas['PlanInfo'] {
	return PLANS.find((row) => row.id === plan) ?? PLANS[0]!;
}

/** The api's limit messages, for the cases the e2e tests reach. */
function limitMessage(kind: 'ai_runs' | 'documents' | 'profiles', state: MockApi): string {
	const plan = limits(state.me.plan);
	if (kind === 'ai_runs')
		return "You have used all of this month's AI usage. Upgrade to Pro for 7 times as much.";
	if (kind === 'documents')
		return `You have ${plan.documents} CVs, the most on ${plan.label}. Delete one or upgrade to Pro for 100.`;
	return `You have ${plan.profiles} profiles, the most on ${plan.label}. Delete one or upgrade to Pro for 10.`;
}

function usageOf(state: MockApi): Schemas['Usage'] {
	const plan = limits(state.me.plan);
	const meter = (kind: 'ai_runs' | 'documents' | 'profiles', used: number) => ({
		used,
		limit: plan[kind],
		message: used >= plan[kind] ? limitMessage(kind, state) : null
	});
	return {
		plan: state.me.plan,
		period_start: '2026-10-01T00:00:00Z',
		period_end: '2026-11-01T00:00:00Z',
		ai_runs: meter('ai_runs', state.aiRuns),
		documents: meter('documents', state.documents.length),
		profiles: meter('profiles', state.profiles.length),
		subscription: state.subscription
	};
}

const AI_MODELS: Schemas['AiModelInfo'][] = [
	{ id: 'mimo-flash', label: 'MiMo Flash', provider: 'mimo', plan: 'free' },
	{ id: 'claude-haiku', label: 'Claude Haiku', provider: 'claude', plan: 'free' },
	{ id: 'gemini-flash-lite', label: 'Gemini Flash-Lite', provider: 'gemini', plan: 'free' },
	{ id: 'mimo-pro', label: 'MiMo Pro', provider: 'mimo', plan: 'pro' },
	{ id: 'gemini-flash', label: 'Gemini Flash', provider: 'gemini', plan: 'pro' },
	{ id: 'claude-sonnet', label: 'Claude Sonnet', provider: 'claude', plan: 'pro' }
];

function modelInfo(id: AiModel) {
	return AI_MODELS.find((model) => model.id === id) ?? AI_MODELS[0]!;
}

const TEMPLATES: TemplateMeta[] = [
	{
		id: 'classic',
		name: 'Classic',
		description: 'Serif',
		paper_sizes: ['a4', 'us-letter'],
		target_pages: 1
	},
	{
		id: 'compact',
		name: 'Compact',
		description: 'Dense',
		paper_sizes: ['a4', 'us-letter'],
		target_pages: 1
	}
];

let counter = 0;
function uuid(): string {
	counter += 1;
	return `00000000-0000-4000-8000-${String(counter).padStart(12, '0')}`;
}

function now(): string {
	return new Date(Date.now() + counter).toISOString();
}

export function starterContent(): CvContent {
	const section = (kind: 'experience' | 'education' | 'skills', title: string) => ({
		id: uuid().slice(-12),
		kind,
		title,
		experience: [],
		projects: [],
		education: [],
		skills: [],
		certifications: [],
		custom: []
	});
	return {
		schema_version: 1,
		basics: { name: '', headline: '', email: '', phone: '', location: '', links: [] },
		summary: '',
		sections: [
			section('experience', 'Experience'),
			section('education', 'Education'),
			section('skills', 'Skills')
		]
	};
}

function placeholders(content: CvContent): { text: string; bullet_id: string | null }[] {
	const found: { text: string; bullet_id: string | null }[] = [];
	const scan = (text: string, bulletId: string | null) => {
		for (const match of text.matchAll(/\[\[(.+?)\]\]/g)) {
			found.push({ text: match[1] ?? '', bullet_id: bulletId });
		}
	};
	scan(content.summary, null);
	for (const section of content.sections) {
		for (const role of section.experience) {
			for (const bullet of role.bullets) scan(bullet.text, bullet.id);
			for (const engagement of role.engagements) {
				for (const bullet of engagement.bullets) scan(bullet.text, bullet.id);
			}
		}
		for (const bullet of section.custom) scan(bullet.text, bullet.id);
	}
	return found;
}

/** A link area the way the renderer draws one for click to edit: a transparent rect in an <a>. */
function sourceLink(target: string, x: number, y: number, width: number): string {
	return `<a transform="translate(${x} ${y})" href="cv:${target}"><rect width="${width}" height="16" fill="transparent"/></a>`;
}

/** A preview page: the name and headline (linked to the header), then each role's bullets, linked
 * to their fields from y 140 down, 20pt apart. */
function page(content: CvContent, template: string): string {
	const clean = (text: string) => text.replace(/[<&]/g, '');
	const bullets = content.sections.flatMap((s) => s.experience.flatMap((role) => role.bullets));
	return (
		'<svg xmlns="http://www.w3.org/2000/svg" width="595.28pt" height="841.89pt" ' +
		`viewBox="0 0 595.28 841.89"><text x="40" y="60">${clean(content.basics.name)}</text>` +
		`<text x="40" y="80">${clean(content.basics.headline)}</text>` +
		sourceLink('basics', 40, 46, 300) +
		`<text x="40" y="100">${template}</text>` +
		bullets
			.map(
				(bullet, i) =>
					`<text x="40" y="${152 + i * 20}">${clean(bullet.text)}</text>` +
					sourceLink(bullet.id, 40, 140 + i * 20, 400)
			)
			.join('') +
		'</svg>'
	);
}

function jobSummary(job: Job) {
	const rest: Partial<Job> = { ...job };
	delete rest.description;
	delete rest.analysis;
	return rest as Omit<Job, 'description' | 'analysis'>;
}

/** What the fake import extracts: one role with one bullet. */
function importedDraft(): CvContent {
	const content = starterContent();
	content.basics.name = 'Ama Owusu-Mensah';
	content.sections[0]?.experience.push({
		id: uuid().slice(-12),
		org: 'Northwind Consulting',
		role: 'Lead data engineer',
		location: 'London, UK',
		dates: { start: '2021-03', end: null },
		stack: ['Python', 'Spark'],
		bullets: [{ id: uuid().slice(-12), text: 'Lead a team of **5 engineers**.', source_id: null }],
		engagements: []
	});
	return content;
}

function bulletDiffs(content: CvContent): BulletDiff[] {
	return content.sections.flatMap((section) =>
		section.experience.flatMap((item) =>
			item.bullets.map((bullet) => ({
				source_id: bullet.id,
				entry: `${item.role}, ${item.org}`,
				source_text: bullet.text,
				text: bullet.text,
				rationale: null
			}))
		)
	);
}

function summary<T extends { content: CvContent }>(row: T): Omit<T, 'content'> {
	const rest: Partial<T> = { ...row };
	delete rest.content;
	return rest as Omit<T, 'content'>;
}

async function reply(route: Route, status: number, body?: unknown, headers = {}) {
	await route.fulfill({
		status,
		headers: { 'content-type': 'application/json', ...headers },
		body: body === undefined ? '' : JSON.stringify(body)
	});
}

/** 402 when the plan has no room for `needed` more, as the api answers. */
function overLimit(
	route: Route,
	state: MockApi,
	kind: 'ai_runs' | 'documents' | 'profiles',
	needed = 1
) {
	const usage = usageOf(state)[kind];
	if (usage.used + needed <= usage.limit) return null;
	return reply(route, 402, {
		error: {
			code: 'quota_exceeded',
			message: limitMessage(kind, state),
			details: { resource: kind }
		}
	});
}

function notFound(route: Route) {
	return reply(route, 404, {
		error: { code: 'not_found', message: 'This does not exist or was deleted.', details: {} }
	});
}

export async function installMockApi(target: Page): Promise<MockApi> {
	const state: MockApi = {
		me: {
			id: uuid(),
			email: 'dev@localhost',
			display_name: null,
			preferred_ai_model: null,
			plan: 'free',
			default_template_id: null
		},
		plansEnforced: true,
		billingEnabled: true,
		aiRuns: 0,
		subscription: null,
		checkouts: 0,
		uploads: [],
		jobs: [],
		aiCalls: [],
		profiles: [],
		documents: [],
		versions: new Map(),
		previewCalls: 0
	};

	await target.route('**/api/v1/**', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		const method = request.method();
		const parts = url.pathname.replace(/^\/api\/v1\//, '').split('/');
		const raw = request.postData() ?? '';
		const multipart = (request.headers()['content-type'] ?? '').startsWith('multipart/');
		const body = raw && !multipart ? JSON.parse(raw) : {};
		const field = (name: string) =>
			new RegExp(`name="${name}"(?:; filename="([^"]*)")?\r\n(?:[^\r]*\r\n)*?\r\n([^\r]*)`).exec(
				raw
			);
		const [resource, id, action, number, subaction] = parts;

		if (resource === 'client-config')
			return reply(route, 200, {
				auth_mode: 'dev',
				firebase: null,
				ai_models: AI_MODELS,
				default_ai_model: 'mimo-flash',
				plans_enforced: state.plansEnforced,
				plans: PLANS,
				billing_enabled: state.billingEnabled
			});

		if (resource === 'usage') return reply(route, 200, usageOf(state));

		if (resource === 'billing') {
			if (id === 'checkout') {
				state.checkouts += 1;
				const ref = `ref_${state.checkouts}`;
				// Paystack sends the user back to the callback URL with the reference.
				return reply(route, 200, {
					authorization_url: `/app/settings?tab=billing&trxref=${ref}&reference=${ref}`
				});
			}
			if (id === 'verify') {
				state.me.plan = 'pro';
				state.subscription = {
					status: 'active',
					current_period_end: '2026-11-10T00:00:00Z',
					manageable: true
				};
				return reply(route, 200, { plan: 'pro' });
			}
			if (id === 'manage-link')
				return reply(route, 200, { url: 'https://paystack.test/manage/subscriptions/SUB_1' });
		}

		if (resource === 'me') {
			if (method === 'PATCH') Object.assign(state.me, body);
			return reply(route, 200, state.me);
		}

		if (resource === 'templates' && id && action === 'preview') {
			const fallback = state.profiles.find((profile) => profile.is_default)?.content;
			const content = fallback?.basics.name
				? fallback
				: { ...starterContent(), basics: { ...starterContent().basics, name: 'Sample' } };
			return reply(route, 200, { pages: [page(content, id)], page_count: 1 });
		}
		if (resource === 'templates') return reply(route, 200, TEMPLATES);

		if (resource === 'uploads') {
			if (method === 'GET') return reply(route, 200, state.uploads);
			const before = state.uploads.length;
			state.uploads = state.uploads.filter((row) => row.id !== id);
			return state.uploads.length < before ? reply(route, 204) : notFound(route);
		}

		if (resource === 'imports' && method === 'POST') {
			const model = (field('ai_model')?.[2] ??
				state.me.preferred_ai_model ??
				'mimo-flash') as AiModel;
			const file = field('file');
			const uploadId = field('upload_id')?.[2];
			const refused = overLimit(route, state, 'ai_runs');
			if (refused) return refused;
			state.aiRuns += 1;
			state.aiCalls.push({ task: 'import', model });
			let upload: UploadSummary | undefined = state.uploads.find((row) => row.id === uploadId);
			if (file) {
				upload = {
					id: uuid(),
					filename: file[1] ?? 'cv.pdf',
					mime_type: 'application/pdf',
					size_bytes: 2048,
					created_at: now()
				};
				state.uploads.unshift(upload);
			}
			return reply(route, 200, {
				upload_id: upload?.id ?? null,
				draft: importedDraft(),
				profile_name: 'Data engineering',
				ai_model: model,
				provider: modelInfo(model).provider,
				model: `fake-${model}`
			});
		}

		if (resource === 'jobs') {
			if (method === 'GET' && !id) return reply(route, 200, state.jobs.map(jobSummary));
			const job = state.jobs.find((row) => row.id === id);
			if (!job) return notFound(route);
			if (method === 'DELETE') {
				state.jobs = state.jobs.filter((row) => row !== job);
				return reply(route, 204);
			}
			return reply(route, 200, job);
		}

		if (resource === 'tailor' && method === 'POST') {
			const profile = state.profiles.find((row) => row.id === body.profile_id);
			if (!profile) return notFound(route);
			const model = (body.ai_model ?? state.me.preferred_ai_model ?? 'mimo-flash') as AiModel;
			let job = state.jobs.find((row) => row.id === body.job_id);
			const refused =
				overLimit(route, state, 'documents') ?? overLimit(route, state, 'ai_runs', job ? 1 : 2);
			if (refused) return refused;
			state.aiRuns += job ? 1 : 2;
			state.aiCalls.push({ task: 'tailor', model });
			if (!job) {
				job = {
					id: uuid(),
					title: body.job.title || 'Senior Data Engineer',
					company: body.job.company || 'Lumen Payments',
					url: body.job.url ?? null,
					description: body.job.description,
					analysis: null,
					created_at: now(),
					updated_at: now()
				};
				state.jobs.unshift(job);
			}
			const doc: CvDocument = {
				id: uuid(),
				name: `${job.title} at ${job.company}`,
				template_id: body.template_id ?? 'classic',
				mode: 'structured',
				page_count: 1,
				profile_id: profile.id,
				job_id: job.id,
				created_at: now(),
				updated_at: now(),
				content: structuredClone(profile.content)
			};
			state.documents.push(doc);
			const result: TailorResult = {
				document: doc,
				job: jobSummary(job),
				ai_model: model,
				provider: modelInfo(model).provider,
				model: `fake-${model}`,
				issues: [],
				changes: bulletDiffs(profile.content),
				dropped: [],
				placeholders: [{ text: 'number of analysts', bullet_id: null }],
				missing_keywords: ['Snowflake']
			};
			return reply(route, 201, result);
		}

		if (resource === 'profiles') {
			if (!id && method === 'GET') {
				const rows = [...state.profiles].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
				return reply(route, 200, rows.map(summary));
			}
			if (!id && method === 'POST') {
				const refused = overLimit(route, state, 'profiles');
				if (refused) return refused;
				const profile: Profile = {
					id: uuid(),
					name: body.name ?? 'Untitled profile',
					is_default: state.profiles.length === 0,
					created_at: now(),
					updated_at: now(),
					content: body.content ?? starterContent()
				};
				state.profiles.push(profile);
				return reply(route, 201, profile);
			}
			const profile = state.profiles.find((row) => row.id === id);
			if (!profile) return notFound(route);
			if (action === 'duplicate') {
				const refused = overLimit(route, state, 'profiles');
				if (refused) return refused;
				const copy = {
					...structuredClone(profile),
					id: uuid(),
					name: `${profile.name} (copy)`,
					is_default: false
				};
				state.profiles.push(copy);
				return reply(route, 201, copy);
			}
			if (method === 'GET') return reply(route, 200, profile);
			if (method === 'PATCH') {
				if (body.is_default) for (const row of state.profiles) row.is_default = false;
				Object.assign(profile, body, { updated_at: now() });
				return reply(route, 200, profile);
			}
			if (method === 'DELETE') {
				state.profiles = state.profiles.filter((row) => row !== profile);
				return reply(route, 204);
			}
		}

		if (resource === 'documents') {
			if (!id && method === 'GET') {
				const rows = [...state.documents].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
				return reply(route, 200, rows.map(summary));
			}
			if (!id && method === 'POST') {
				const profile = state.profiles.find((row) => row.id === body.profile_id);
				if (!profile) return notFound(route);
				const refused = overLimit(route, state, 'documents');
				if (refused) return refused;
				const doc: CvDocument = {
					id: uuid(),
					name: body.name ?? `${profile.name} CV`,
					template_id: body.template_id ?? 'classic',
					mode: 'structured',
					page_count: null,
					profile_id: profile.id,
					job_id: null,
					created_at: now(),
					updated_at: now(),
					content: structuredClone(profile.content)
				};
				state.documents.push(doc);
				return reply(route, 201, doc);
			}
			const doc = state.documents.find((row) => row.id === id);
			if (!doc) return notFound(route);
			const versions = state.versions.get(doc.id) ?? [];
			state.versions.set(doc.id, versions);
			const snapshot = (reason: Version['reason']) => {
				const version = {
					number: versions.length + 1,
					reason,
					created_at: now(),
					content: structuredClone(doc.content)
				};
				versions.push(version);
				return version;
			};

			if (action === 'preview') {
				state.previewCalls += 1;
				doc.page_count = 1;
				return reply(route, 200, { pages: [page(doc.content, doc.template_id)], page_count: 1 });
			}
			if (action === 'export.pdf') {
				const left = placeholders(doc.content);
				if (left.length && url.searchParams.get('force') !== 'true') {
					return reply(route, 409, {
						error: {
							code: 'conflict',
							message: `This CV still has ${left.length} placeholders.`,
							details: { placeholders: left }
						}
					});
				}
				return route.fulfill({
					status: 200,
					headers: {
						'content-type': 'application/pdf',
						'content-disposition': `attachment; filename="${doc.content.basics.name.replace(/\s+/g, '-')}-CV.pdf"`
					},
					body: '%PDF-1.7\n%mock\n'
				});
			}
			if (action === 'duplicate') {
				const refused = overLimit(route, state, 'documents');
				if (refused) return refused;
				const copy = { ...structuredClone(doc), id: uuid(), name: `${doc.name} (copy)` };
				state.documents.push(copy);
				return reply(route, 201, copy);
			}
			if (action === 'versions' && !number && method === 'GET') {
				return reply(route, 200, [...versions].reverse().map(summary));
			}
			if (action === 'versions' && !number && method === 'POST') {
				return reply(route, 201, summary(snapshot('manual')));
			}
			if (action === 'versions' && subaction === 'restore') {
				const version = versions.find((row) => row.number === Number(number));
				if (!version) return notFound(route);
				snapshot('autosave');
				doc.content = structuredClone(version.content);
				doc.updated_at = now();
				snapshot('restore');
				return reply(route, 200, doc);
			}
			if (method === 'GET') return reply(route, 200, doc);
			if (method === 'PATCH') {
				Object.assign(doc, body, { updated_at: now() });
				return reply(route, 200, doc);
			}
			if (method === 'DELETE') {
				state.documents = state.documents.filter((row) => row !== doc);
				return reply(route, 204);
			}
		}

		return notFound(route);
	});

	return state;
}

/** Playwright test with the mock api installed on every page. */
export const test = base.extend<{ api: MockApi }>({
	api: [
		async ({ page }, use) => {
			await use(await installMockApi(page));
		},
		{ auto: true }
	]
});

export { expect } from '@playwright/test';
