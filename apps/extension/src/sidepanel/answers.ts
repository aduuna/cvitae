import type { Schemas } from '@web/api/client.ts';
import type { JobDraft, QuestionInfo } from '../content/types.ts';
import { fitLines } from '../content/values.ts';
import type { AnswersRequest } from '../lib/api.ts';
import type { FrameScan } from '../lib/page.ts';
import type { SourceRef } from '../lib/settings.ts';
import { plural } from './review.ts';

/** Drafted answers as the Answer questions card shows them (docs/PRODUCT.md, 8). */

export type FinishedAnswer = Schemas['FinishedAnswer'];
export type InferredSkill = Schemas['InferredSkill'];

export interface DraftRow {
	text: string;
	inferred: InferredSkill[];
	shortened: boolean;
	/** Fill it: ticked unless the field has a value or nothing was drafted. */
	fill: boolean;
}

/** A question found on the page, and its draft once there is one. */
export interface QuestionRow {
	/** Unique across frames; the id the api gets. */
	key: string;
	frameId: number;
	question: QuestionInfo;
	/** Draft it: ticked unless the field has a value. */
	draft: boolean;
	answer: DraftRow | null;
}

/** What the drafts are written from, besides the profile or CV. */
export type JobContext =
	| { kind: 'saved'; id: string; title: string; company: string }
	| { kind: 'page'; draft: JobDraft }
	| { kind: 'none' };

/** As many questions as one request takes; each frame is read for at most as many. */
const MAX_QUESTIONS = 20;

export function questionRows(frames: FrameScan[]): QuestionRow[] {
	return frames
		.flatMap(({ frameId, scan }) =>
			scan.questions.map((question) => ({
				key: `${frameId}:${question.id}`,
				frameId,
				question,
				draft: !question.filled,
				answer: null
			}))
		)
		.slice(0, MAX_QUESTIONS);
}

/** The first frame's sentence asking applicants not to use AI, if any frame has one. */
export function aiPolicyOf(frames: FrameScan[]): string | null {
	return frames.map(({ scan }) => scan.aiPolicy).find((policy) => policy) ?? null;
}

const number = (n: number) => n.toLocaleString('en-US');

/** "1 word", "1,000 characters": a count with thousands separators. */
function counted(n: number, one: string): string {
	return `${number(n)} ${n === 1 ? one : `${one}s`}`;
}

/** "200 words", "1,000 characters", or both. */
export function limitText(question: QuestionInfo): string {
	return [
		question.maxWords ? counted(question.maxWords, 'word') : '',
		question.maxChars ? counted(question.maxChars, 'character') : ''
	]
		.filter(Boolean)
		.join(', ');
}

export function wordCount(text: string): number {
	return text.split(/\s+/).filter(Boolean).length;
}

/** "143 of 200 words", and whether the text is over a limit. */
export function countText(text: string, question: QuestionInfo): { text: string; over: boolean } {
	const words = wordCount(text);
	if (question.maxWords) {
		return {
			text: `${number(words)} of ${counted(question.maxWords, 'word')}`,
			over: words > question.maxWords
		};
	}
	if (question.maxChars) {
		return {
			text: `${number(text.length)} of ${counted(question.maxChars, 'character')}`,
			over: text.length > question.maxChars
		};
	}
	return { text: counted(words, 'word'), over: false };
}

function list(items: string[]): string {
	return items.length < 2
		? (items[0] ?? '')
		: `${items.slice(0, -1).join(', ')} and ${items.at(-1)}`;
}

/**
 * The hint under a draft: the skills it names that the material does not, and what they rest on.
 * "Mentions dbt, from your Spark and Databricks work."
 */
export function hintText(inferred: InferredSkill[], source: string): string {
	const [only] = inferred;
	if (!only) return '';
	if (inferred.length === 1) {
		return only.based_on.length
			? `Mentions ${only.skill}, from your ${list(only.based_on)} work.`
			: `Mentions ${only.skill}, which your ${source} does not name.`;
	}
	const named = inferred.map((skill) =>
		skill.based_on.length ? `${skill.skill} (from your ${list(skill.based_on)} work)` : skill.skill
	);
	return `Mentions ${list(named)}.`;
}

/** "From your Data engineering profile and the job ad you saved for Data engineer at Harbour Bank." */
export function contextText(source: string, job: JobContext): string {
	if (job.kind === 'saved') {
		const what = [job.title || 'this job', job.company].filter(Boolean).join(' at ');
		return `From your ${source} and the job ad you saved for ${what}.`;
	}
	if (job.kind === 'page') return `From your ${source} and the job ad on this page.`;
	return `From your ${source}. No job ad found here, so answers about the company will have gaps.`;
}

/** The api's limits on a question's text and on the draft a Redraft replaces. */
const MAX_TEXT = 1000;
const MAX_PREVIOUS = 5000;

/** The question as the api takes it: the label, then any help text the form gives. */
function asked(question: QuestionInfo): string {
	const text =
		question.help && !question.label.includes(question.help)
			? `${question.label}\n${question.help}`
			: question.label;
	return text.slice(0, MAX_TEXT);
}

/** One request for the rows: their questions, the source and the job ad. */
export function draftRequest(
	source: SourceRef,
	rows: QuestionRow[],
	job: JobContext,
	previous: Record<string, string> = {}
): AnswersRequest {
	return {
		source,
		job_id: job.kind === 'saved' ? job.id : null,
		job:
			job.kind === 'page'
				? {
						description: job.draft.description,
						title: job.draft.title,
						company: job.draft.company
					}
				: null,
		questions: rows.map((row) => ({
			id: row.key,
			text: asked(row.question),
			multiline: row.question.multiline,
			max_words: row.question.maxWords,
			max_chars: row.question.maxChars,
			previous: previous[row.key]?.slice(0, MAX_PREVIOUS) ?? null
		})),
		ai_model: null
	};
}

export function draftOf(answer: FinishedAnswer, question: QuestionInfo): DraftRow {
	return {
		text: answer.text,
		inferred: answer.inferred,
		shortened: answer.shortened,
		fill: answer.text.trim() !== '' && !question.filled
	};
}

/** The text that goes into the field: cut to its length limit, as filling from the profile is. */
export function fillValue(row: QuestionRow): string {
	return fitLines(row.answer?.text ?? '', row.question.maxLength).text;
}

/** The ticked drafts, per frame, as the content script takes them. */
export function answersByFrame(
	rows: QuestionRow[]
): [number, { fieldId: string; value: string }[]][] {
	const frames = new Map<number, { fieldId: string; value: string }[]>();
	for (const row of rows) {
		if (!row.answer?.fill || !row.answer.text.trim()) continue;
		frames.set(row.frameId, [
			...(frames.get(row.frameId) ?? []),
			{ fieldId: row.question.id, value: fillValue(row) }
		]);
	}
	return [...frames];
}

const PLACEHOLDER = /\[\[[^\]]*\]\]/g;

/** What the user should know before filling: shortened drafts and gaps still to fill. */
export function answerNotes(rows: QuestionRow[]): string[] {
	const drafted = rows.filter((row) => row.answer);
	const notes: string[] = [];
	const shortened = drafted.filter((row) => row.answer?.shortened).length;
	if (shortened) {
		notes.push(`${plural(shortened, 'answer was', 'answers were')} shortened to fit the limit.`);
	}
	const gaps = drafted.reduce(
		(sum, row) => sum + (row.answer?.text.match(PLACEHOLDER)?.length ?? 0),
		0
	);
	if (gaps) {
		notes.push(
			`The answers have ${plural(gaps, 'placeholder')} in square brackets. Replace ${gaps === 1 ? 'it' : 'them'} with real details before you submit.`
		);
	}
	return notes;
}
