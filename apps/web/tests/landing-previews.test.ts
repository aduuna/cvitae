// @vitest-environment node
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { landingTemplates } from '#lib/components/landing/templates.ts';

const web = fileURLToPath(new URL('..', import.meta.url));
const repo = fileURLToPath(new URL('../../..', import.meta.url));

// The api image builds the SPA from apps/web alone, so the landing page carries copies of the
// template previews. They must match the renders in templates/.
describe('landing page template pictures', () => {
	it.each(landingTemplates.map((template) => template.id))('%s matches its preview', (id) => {
		const copy = readFileSync(`${web}static/landing/${id}.png`);
		const preview = readFileSync(`${repo}templates/${id}/preview.png`);
		expect(
			copy.equals(preview),
			`static/landing/${id}.png is stale: cp templates/${id}/preview.png apps/web/static/landing/${id}.png`
		).toBe(true);
	});
});
