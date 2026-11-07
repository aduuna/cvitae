import { words, type Described } from './classify.ts';

/**
 * Open questions on an application form, which the user can have drafted (docs/PRODUCT.md, 8,
 * Answer questions): free-text fields the profile does not fill, whose label reads as a question.
 */

/** Room for a sentence: a single-line field with a tighter limit takes a word or a number. */
const MIN_ROOM = 100;
const LONG_LABEL_WORDS = 6;

/** Words a question starts with: "Why ...", "Describe ...", "In a few sentences, ...". */
const QUESTION_START =
	/^(why|what|how|when|where|which|who|describe|tell|explain|share|give|walk|provide|outline|summari[sz]e|list|please|briefly|in (a|one|two|three|few|\d+)|can you|could you|do you|have you|are you|would you|if you|is there)\b/;

/**
 * Questions never drafted: what the user alone can answer (equal opportunity monitoring,
 * eligibility, pay, dates, referrals, other people's details) and what Chameleon vitae does not
 * write (cover letters). Narrower than the classifier's list: "How did you handle ..." and "Why do
 * you want ..." are questions to draft.
 */
const NEVER_ANSWER =
	/\b(gender|sex|sexual|sexuality|race(?! condition)|racial|ethnic\w*|hispanic|latin[oax]|veteran|disabilit\w*|disabled|pronouns?|religio\w*|birth|dob|age|nationality|citizen\w*|visa|sponsor\w*|authori[sz]ed to work|work authori[sz]ation|eligib\w*|right to work|clearance|salary|compensation|pay|wage|day rate|hourly rate|rate of pay|notice period|start date|when can you start|available to start|your availability|availability to (start|interview)|relocat\w*|referr\w*|referral|references?|hear about|how did you (hear|find|learn|come across)|recruiter|emergency|cover letter|captcha|password|coupon|promo|years of experience|how many years|signature|sign here|consent|agree|acknowledge|terms and conditions|terms of (use|service)|privacy (policy|notice)|gdpr|(home|street|postal|mailing|email) address|address line|post ?code|zip)\b/;

/** Inputs that take a sentence. */
const TEXT_TYPES = new Set(['text', '']);

/** Whether a field the classifier left alone is an open question to draft. */
export function isQuestion(field: Described): boolean {
	const textArea = field.tag === 'textarea';
	const textInput =
		field.tag === 'input' &&
		TEXT_TYPES.has(field.type) &&
		(field.maxLength === null || field.maxLength >= MIN_ROOM);
	if ((!textArea && !textInput) || field.needsChoice) return false;
	const label = field.label.trim();
	const said = words(label);
	if (!said) return false;
	const all = [said, words(field.placeholder), ...field.hints.map(words)].join(' ');
	if (NEVER_ANSWER.test(all)) return false;
	return (
		label.endsWith('?') || QUESTION_START.test(said) || said.split(' ').length >= LONG_LABEL_WORDS
	);
}

const LIMIT = /(\d[\d,]*)\s*(?:(?:-|\u2013|to)\s*(\d[\d,]*)\s*)?(words?|characters?|chars?)\b/gi;
const MINIMUM = /\b(at least|minimum( of)?|min\.?|more than|over)\s*$/i;

/** Limits a question states, such as "in 200 words", "max 1,000 characters" or "150 to 300
 * words" (the upper bound). Minimums ("at least 100 words") are left to the question's text. */
export function statedLimits(text: string): { words: number | null; chars: number | null } {
	let maxWords: number | null = null;
	let maxChars: number | null = null;
	for (const match of text.matchAll(LIMIT)) {
		if (MINIMUM.test(text.slice(Math.max(0, match.index - 20), match.index))) continue;
		const value = Number((match[2] ?? match[1] ?? '').replace(/,/g, ''));
		if (!Number.isFinite(value) || value <= 0) continue;
		if (/^w/i.test(match[3] ?? '')) maxWords = Math.min(maxWords ?? value, value);
		else maxChars = Math.min(maxChars ?? value, value);
	}
	return { words: maxWords, chars: maxChars };
}

const MENTIONS_AI =
	/\b(ai|a\.i\.|artificial intelligence|generative ai|genai|chat ?gpt|gpt|llms?|large language models?)\b/i;
const FORBIDS =
	/\b(do not|don't|must not|mustn't|should not|shouldn't|may not|cannot|can't|never|not (be )?(allowed|permitted|accepted|considered)|prohibited|forbidden|refrain|avoid|without (the )?(use|help|assistance)|disqualif\w*|rejected|in your own words)\b/i;
const ABOUT_APPLYING =
	/\b(answers?|responses?|applications?|apply|applying|questions?|cover letters?|write|writing|written|submissions?|assessments?)\b/i;
/** "We do not use AI to screen applications" is about the employer, not the applicant. */
const ABOUT_EMPLOYER = /\b(we|our)\s+(do not|don't|never|will not|won't)\s+use\b/i;

const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'svg']);
const MAX_TEXT = 200_000;
const MAX_QUOTE = 200;

function pageText(root: Node): string {
	let text = '';
	const walk = (node: Node) => {
		for (const child of node.childNodes) {
			if (text.length > MAX_TEXT) return;
			if (child.nodeType === Node.TEXT_NODE) text += child.textContent ?? '';
			else if (child instanceof Element && !SKIP.has(child.tagName) && !child.closest('[hidden]')) {
				walk(child);
				text += ' ';
			}
		}
	};
	walk(root);
	return text.replace(/\s+/g, ' ');
}

/** A sentence on the page that asks applicants not to use AI, quoted, or null. */
export function aiPolicy(doc: Document): string | null {
	if (!doc.body) return null;
	const sentences = pageText(doc.body).split(/(?<=[.!?])\s+/);
	const found = sentences.find(
		(sentence) =>
			MENTIONS_AI.test(sentence) &&
			FORBIDS.test(sentence) &&
			ABOUT_APPLYING.test(sentence) &&
			!ABOUT_EMPLOYER.test(sentence)
	);
	if (!found) return null;
	const quote = found.trim();
	return quote.length > MAX_QUOTE ? `${quote.slice(0, MAX_QUOTE).trimEnd()}...` : quote;
}
