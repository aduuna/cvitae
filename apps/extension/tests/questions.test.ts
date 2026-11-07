import { describe, expect, it } from 'vitest';
import type { Described } from '../src/content/classify.ts';
import { element, scan } from '../src/content/fields.ts';
import { fillFields, undoFill } from '../src/content/fill.ts';
import { aiPolicy, isQuestion, statedLimits } from '../src/content/questions.ts';
import { loadFixture } from './helpers.ts';

function described(overrides: Partial<Described> = {}): Described {
	return {
		tag: 'textarea',
		type: 'textarea',
		label: '',
		context: '',
		hints: [],
		autocomplete: '',
		placeholder: '',
		maxLength: null,
		options: null,
		filled: false,
		needsChoice: false,
		...overrides
	};
}

describe('open questions', () => {
	it('lists the questions to draft and leaves out the rest', () => {
		loadFixture('questions');

		const page = scan();

		expect(page.questions.map((q) => q.label)).toEqual([
			'Describe a time you used dbt in production.',
			'Why do you want to work at Harbour Bank?',
			'Tell us about a project you are proud of',
			'How did you handle a disagreement with your manager?'
		]);
		// Filling from the profile still covers its own fields.
		expect(page.fields.map((f) => f.kind)).toEqual(['name.first', 'email', 'link.linkedin']);
	});

	it('reads limits, help text, the field kind and whether it has a value', () => {
		loadFixture('questions');

		const [dbt, why, project, conflict] = scan().questions;

		expect(dbt).toMatchObject({
			help: 'Please answer in 150 to 200 words.',
			multiline: true,
			maxWords: 200,
			maxChars: null,
			filled: false
		});
		expect(why).toMatchObject({ multiline: false, maxWords: null, maxChars: null });
		// The tighter of the field's limit and the one its placeholder states.
		expect(project).toMatchObject({ maxLength: 1000, maxChars: 800 });
		expect(conflict?.filled).toBe(true);
	});

	it('gives each question an id the fill can use', () => {
		loadFixture('questions');
		const [dbt] = scan().questions;

		expect(element(dbt!.id)).toBe(document.getElementById('q_dbt'));
		expect(scan().questions[0]?.id).toBe(dbt!.id);
	});

	it('finds the questions of the fixtures from the main job platforms', () => {
		const found = (name: string) => {
			loadFixture(name);
			return scan().questions.map((q) => [q.label, q.maxWords ?? q.maxChars ?? q.maxLength]);
		};

		// Each page also has fields that are never drafted (how you heard, authorization, notice
		// period, salary, visa, pronouns, a disabled field), ones the profile fills, and one that is
		// hidden: none of those are listed.
		expect(found('greenhouse')).toEqual([['Why are you interested in working at Acme?', 200]]);
		expect(found('greenhouse-new')).toEqual([['Why do you want to join us?', null]]);
		expect(found('lever')).toEqual([
			['Describe a project where you improved a data pipeline.', 1500]
		]);
		expect(found('ashby')).toEqual([['Why are you interested in this role?', 1000]]);
		expect(found('careers')).toEqual([['What motivates you to apply for this role?', 500]]);
		expect(found('workday')).toEqual([]);
	});

	it('reads labels as questions', () => {
		const question = (label: string, more: Partial<Described> = {}) =>
			isQuestion(described({ label, ...more }));

		expect(question('What excites you about this role?')).toBe(true);
		expect(question('Describe your experience with Kafka')).toBe(true);
		expect(question('In a few sentences, introduce your best work')).toBe(true);
		expect(question('A project that shows how you work with others')).toBe(true);
		expect(question('How would you address technical debt?')).toBe(true);
		expect(question('How have you designed for high availability?')).toBe(true);
		expect(question('Comments')).toBe(false);
		expect(question('')).toBe(false);
	});

	it('never takes the questions only the applicant can answer', () => {
		const question = (label: string) => isQuestion(described({ label }));

		for (const label of [
			'What is your gender?',
			'Do you require visa sponsorship?',
			'Are you authorized to work in the UK?',
			'What is your expected salary?',
			'What is your notice period?',
			'When can you start?',
			'Who referred you?',
			'How did you find this job?',
			'Please provide two references',
			'Please paste your cover letter',
			'Are you willing to relocate?',
			'What is your home address?'
		]) {
			expect(question(label), label).toBe(false);
		}
		expect(isQuestion(described({ label: 'Tell us more?', hints: ['cover_letter_text'] }))).toBe(
			false
		);
	});

	it('takes text areas and text fields with room for a sentence', () => {
		const label = 'Why do you want to join?';

		expect(isQuestion(described({ label }))).toBe(true);
		expect(isQuestion(described({ label, tag: 'input', type: 'text' }))).toBe(true);
		expect(isQuestion(described({ label, tag: 'input', type: 'text', maxLength: 100 }))).toBe(true);
		expect(isQuestion(described({ label, tag: 'input', type: 'text', maxLength: 60 }))).toBe(false);
		expect(isQuestion(described({ label, tag: 'input', type: 'email' }))).toBe(false);
		expect(isQuestion(described({ label, tag: 'select', type: 'select' }))).toBe(false);
		expect(isQuestion(described({ label, needsChoice: true }))).toBe(false);
	});
});

describe('statedLimits', () => {
	it('reads word and character limits', () => {
		expect(statedLimits('Answer in 200 words')).toEqual({ words: 200, chars: null });
		expect(statedLimits('Max 1,000 characters')).toEqual({ words: null, chars: 1000 });
		expect(statedLimits('150-300 words')).toEqual({ words: 300, chars: null });
		expect(statedLimits('150 to 300 words, 2000 chars')).toEqual({ words: 300, chars: 2000 });
		expect(statedLimits('Between 100 \u2013 250 words')).toEqual({ words: 250, chars: null });
	});

	it('leaves minimums and other numbers alone', () => {
		expect(statedLimits('At least 100 words')).toEqual({ words: null, chars: null });
		expect(statedLimits('Minimum of 50 words, up to 300 words')).toEqual({
			words: 300,
			chars: null
		});
		expect(statedLimits('Your top 3 projects')).toEqual({ words: null, chars: null });
	});
});

describe('aiPolicy', () => {
	it('quotes a sentence that asks applicants not to use AI', () => {
		loadFixture('questions');

		expect(aiPolicy(document)).toBe(
			'Please write your answers yourself: applications that use AI tools to write answers will not be considered.'
		);
		expect(scan().aiPolicy).toBe(aiPolicy(document));
	});

	it('ignores AI in the job and in what the employer does', () => {
		document.body.innerHTML = `
			<p>You will build AI products and must not be afraid of ambiguity.</p>
			<p>We do not use AI to screen applications.</p>
			<p hidden>Do not use ChatGPT to write your answers.</p>
			<textarea aria-label="Why do you want to join us?"></textarea>`;

		expect(aiPolicy(document)).toBeNull();
	});

	it('is read only when the page has questions', () => {
		document.body.innerHTML = `<p>Do not use AI to write your answers.</p>
			<input aria-label="Email" type="email" />`;

		expect(scan().aiPolicy).toBeNull();
	});
});

describe('fill batches', () => {
	it('undoes answers and fields separately', () => {
		loadFixture('questions');
		const page = scan();
		const email = page.fields.find((f) => f.kind === 'email')!;
		const [dbt] = page.questions;

		fillFields([{ fieldId: email.id, value: 'ama@example.com' }], element);
		fillFields([{ fieldId: dbt!.id, value: 'At Northwind I ...' }], element, 'answers');

		expect(undoFill('answers')).toBe(1);
		expect((document.getElementById('q_dbt') as HTMLTextAreaElement).value).toBe('');
		expect((document.getElementById('email') as HTMLInputElement).value).toBe('ama@example.com');
		expect(undoFill()).toBe(1);
		expect((document.getElementById('email') as HTMLInputElement).value).toBe('');
		expect(undoFill('answers')).toBe(0);
	});
});
