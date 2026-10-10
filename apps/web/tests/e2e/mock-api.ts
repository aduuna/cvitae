import { test as base, type Page, type Route } from '@playwright/test';
import type {
	CvContent,
	CvDocument,
	Profile,
	TemplateMeta,
	Version
} from '../../src/lib/cv/types.ts';

/**
 * An in-memory stand-in for the api, installed with page.route. It keeps state across reloads
 * within a test and follows the real endpoints closely enough for the editor flows.
 */
export interface MockApi {
	profiles: Profile[];
	documents: CvDocument[];
	versions: Map<string, (Version & { content: CvContent })[]>;
	previewCalls: number;
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

function starterContent(): CvContent {
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

function page(content: CvContent, template: string): string {
	const name = content.basics.name.replace(/[<&]/g, '');
	const headline = content.basics.headline.replace(/[<&]/g, '');
	return (
		'<svg xmlns="http://www.w3.org/2000/svg" width="595.28pt" height="841.89pt" ' +
		`viewBox="0 0 595.28 841.89"><text x="40" y="60">${name}</text>` +
		`<text x="40" y="80">${headline}</text><text x="40" y="100">${template}</text></svg>`
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

function notFound(route: Route) {
	return reply(route, 404, {
		error: { code: 'not_found', message: 'This does not exist or was deleted.', details: {} }
	});
}

export async function installMockApi(target: Page): Promise<MockApi> {
	const state: MockApi = { profiles: [], documents: [], versions: new Map(), previewCalls: 0 };

	await target.route('**/api/v1/**', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		const method = request.method();
		const parts = url.pathname.replace(/^\/api\/v1\//, '').split('/');
		const body = request.postData() ? JSON.parse(request.postData() ?? '{}') : {};
		const [resource, id, action, number, subaction] = parts;

		if (resource === 'templates') return reply(route, 200, TEMPLATES);

		if (resource === 'profiles') {
			if (!id && method === 'GET') {
				const rows = [...state.profiles].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
				return reply(route, 200, rows.map(summary));
			}
			if (!id && method === 'POST') {
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
