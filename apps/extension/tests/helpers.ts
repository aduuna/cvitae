import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { ApplicationData, FieldInfo, PageScan } from '../src/content/types.ts';
import sample from './fixtures/application-sample.json';

/** Put a fixture form into the test document. */
export function loadFixture(name: string): void {
	document.head.innerHTML = '';
	document.body.innerHTML = readFileSync(
		join(import.meta.dirname, 'fixtures', `${name}.html`),
		'utf8'
	);
}

/** The api's application data for templates/fixtures/profile-sample.json. */
export function sampleData(): ApplicationData {
	return structuredClone(sample) as ApplicationData;
}

/** A field described as the content script would, for tests of pure functions. */
export function field(overrides: Partial<FieldInfo> = {}): FieldInfo {
	return {
		id: 'f1',
		tag: 'input',
		type: 'text',
		label: '',
		context: '',
		hints: [],
		autocomplete: '',
		placeholder: '',
		maxLength: null,
		options: null,
		filled: false,
		needsChoice: false,
		kind: null,
		part: null,
		group: 0,
		...overrides
	};
}

/** label: kind (part) #group, for compact assertions on a scan. */
export function summary(scan: PageScan): string[] {
	return scan.fields.map(
		(f) => `${f.label}: ${f.kind}${f.part ? ` (${f.part})` : ''}${f.group ? ` #${f.group}` : ''}`
	);
}
