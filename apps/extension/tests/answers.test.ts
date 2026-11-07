import { describe, expect, it } from 'vitest';
import type { PageScan, QuestionInfo } from '../src/content/types.ts';
import {
	aiPolicyOf,
	answerNotes,
	answersByFrame,
	contextText,
	countText,
	draftOf,
	draftRequest,
	hintText,
	limitText,
	questionRows,
	type QuestionRow
} from '../src/sidepanel/answers.ts';

function question(overrides: Partial<QuestionInfo> = {}): QuestionInfo {
	return {
		id: 'f1',
		label: 'Why do you want to join us?',
		help: '',
		multiline: true,
		maxLength: null,
		maxWords: null,
		maxChars: null,
		filled: false,
		...overrides
	};
}

function frame(frameId: number, questions: QuestionInfo[], aiPolicy: string | null = null) {
	const scan: PageScan = { url: '', title: '', fields: [], files: [], questions, aiPolicy };
	return { frameId, scan };
}

function drafted(text: string, overrides: Partial<QuestionInfo> = {}, frameId = 0): QuestionRow {
	const info = question(overrides);
	const [row] = questionRows([frame(frameId, [info])]);
	return {
		...row!,
		answer: draftOf({ id: row!.key, text, inferred: [], placeholders: 0, shortened: false }, info)
	};
}

describe('questions from the page', () => {
	it('keys questions by frame, and ticks those without a value', () => {
		const rows = questionRows([
			frame(0, [question({ id: 'f1' })]),
			frame(3, [question({ id: 'f1' }), question({ id: 'f2', filled: true })])
		]);

		expect(rows.map((row) => [row.key, row.draft])).toEqual([
			['0:f1', true],
			['3:f1', true],
			['3:f2', false]
		]);
	});

	it('lists no more questions than one request takes', () => {
		const many = (prefix: string) =>
			Array.from({ length: 12 }, (_, n) => question({ id: `${prefix}${n}` }));

		const rows = questionRows([frame(0, many('a')), frame(1, many('b'))]);

		expect(rows).toHaveLength(20);
		expect(rows.at(-1)?.key).toBe('1:b7');
	});

	it('takes the first frame that has an AI notice', () => {
		expect(aiPolicyOf([frame(0, []), frame(2, [], 'Do not use AI.')])).toBe('Do not use AI.');
		expect(aiPolicyOf([frame(0, [])])).toBeNull();
	});
});

describe('limits and counts', () => {
	it('names the limits', () => {
		expect(limitText(question({ maxWords: 200 }))).toBe('200 words');
		expect(limitText(question({ maxChars: 1000 }))).toBe('1,000 characters');
		expect(limitText(question({ maxWords: 1, maxChars: 500 }))).toBe('1 word, 500 characters');
		expect(limitText(question())).toBe('');
	});

	it('counts against the limit', () => {
		expect(countText('one two three', question({ maxWords: 2 }))).toEqual({
			text: '3 of 2 words',
			over: true
		});
		expect(countText('abc', question({ maxChars: 1200 }))).toEqual({
			text: '3 of 1,200 characters',
			over: false
		});
		expect(countText('  one  two ', question())).toEqual({ text: '2 words', over: false });
	});
});

describe('hintText', () => {
	it('names what a skill rests on, as a hint', () => {
		expect(hintText([{ skill: 'dbt', based_on: ['Spark', 'Databricks'] }], 'profile')).toBe(
			'Mentions dbt, from your Spark and Databricks work.'
		);
		expect(hintText([{ skill: 'Looker', based_on: [] }], 'CV')).toBe(
			'Mentions Looker, which your CV does not name.'
		);
		expect(
			hintText(
				[
					{ skill: 'dbt', based_on: ['Spark', 'Airflow', 'BigQuery'] },
					{ skill: 'Looker', based_on: [] }
				],
				'profile'
			)
		).toBe('Mentions dbt (from your Spark, Airflow and BigQuery work) and Looker.');
		expect(hintText([], 'profile')).toBe('');
	});
});

describe('contextText', () => {
	it('says what the drafts are written from', () => {
		expect(
			contextText('Data profile', {
				kind: 'saved',
				id: 'j1',
				title: 'Data engineer',
				company: 'Harbour Bank'
			})
		).toBe('From your Data profile and the job ad you saved for Data engineer at Harbour Bank.');
		expect(
			contextText('Data profile', {
				kind: 'page',
				draft: { title: '', company: '', url: '', description: 'Ad', from: 'posting' }
			})
		).toBe('From your Data profile and the job ad on this page.');
		expect(contextText('Data profile', { kind: 'none' })).toBe(
			'From your Data profile. No job ad found here, so answers about the company will have gaps.'
		);
	});
});

describe('draftRequest', () => {
	it('sends the questions with their help text and limits, and the job ad', () => {
		const rows = questionRows([
			frame(1, [
				question({ id: 'f4', help: 'In 200 words.', maxWords: 200, multiline: false }),
				question({ id: 'f5', label: 'Describe a project (in 200 words).', help: 'in 200 words' })
			])
		]);
		const ad = {
			title: 'Analyst',
			company: 'Acme',
			url: 'u',
			description: 'Ad',
			from: 'page' as const
		};

		const body = draftRequest(
			{ kind: 'document', id: 'd1' },
			rows,
			{ kind: 'page', draft: ad },
			{
				'1:f4': 'Old draft'
			}
		);

		expect(body).toEqual({
			source: { kind: 'document', id: 'd1' },
			job_id: null,
			job: { description: 'Ad', title: 'Analyst', company: 'Acme' },
			questions: [
				{
					id: '1:f4',
					text: 'Why do you want to join us?\nIn 200 words.',
					multiline: false,
					max_words: 200,
					max_chars: null,
					previous: 'Old draft'
				},
				{
					id: '1:f5',
					text: 'Describe a project (in 200 words).',
					multiline: true,
					max_words: null,
					max_chars: null,
					previous: null
				}
			],
			ai_model: null
		});
		const long = draftRequest(
			{ kind: 'profile', id: 'p1' },
			rows.slice(0, 1),
			{ kind: 'none' },
			{ '1:f4': 'x'.repeat(6000) }
		);
		expect(long.questions[0]?.previous).toHaveLength(5000);
		expect(
			draftRequest({ kind: 'profile', id: 'p1' }, rows, {
				kind: 'saved',
				id: 'j1',
				title: '',
				company: ''
			})
		).toMatchObject({ job_id: 'j1', job: null });
	});
});

describe('filling drafts', () => {
	it('fills ticked drafts with text, cut to the field length', () => {
		const long = drafted('First line.\nSecond line that is long.', { id: 'f1', maxLength: 12 });
		const unticked = drafted('Keep out.', { id: 'f2' });
		unticked.answer!.fill = false;
		const elsewhere = drafted('Other frame.', { id: 'f1' }, 4);

		expect(answersByFrame([long, unticked, elsewhere])).toEqual([
			[0, [{ fieldId: 'f1', value: 'First line.' }]],
			[4, [{ fieldId: 'f1', value: 'Other frame.' }]]
		]);
	});

	it('leaves empty drafts and fields with a value unticked', () => {
		expect(drafted('').answer?.fill).toBe(false);
		expect(drafted('An answer.', { filled: true }).answer?.fill).toBe(false);
		expect(drafted('An answer.').answer?.fill).toBe(true);
	});

	it('notes shortened answers and gaps', () => {
		const gap = drafted('I led [[how many]] people and [[what]].');
		const short = drafted('Short.');
		short.answer!.shortened = true;

		expect(answerNotes([gap, short])).toEqual([
			'1 answer was shortened to fit the limit.',
			'The answers have 2 placeholders in square brackets. Replace them with real details before you submit.'
		]);
		expect(answerNotes([drafted('Fine.')])).toEqual([]);
	});
});
