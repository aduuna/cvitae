/**
 * Rich text for display: `**bold**` and `[[placeholder]]`, everything else literal. A port of
 * `cvcore.richtext.parse` with the same rules; the tests share its cases.
 */
export interface Span {
	t: string;
	b: boolean;
	p: boolean;
}

const BOLD = '**';
const OPEN = '[[';
const CLOSE = ']]';

export function parseRich(text: string): Span[] {
	const spans: Span[] = [];
	let literal = '';
	let i = 0;
	let boldEnd = -1;

	const flush = () => {
		if (literal) spans.push({ t: literal, b: false, p: false });
		literal = '';
	};

	while (i < text.length) {
		if (text.startsWith(BOLD, i) && i !== boldEnd) {
			const close = text.indexOf(BOLD, i + BOLD.length + 1);
			if (close !== -1) {
				flush();
				spans.push(...placeholders(text.slice(i + BOLD.length, close), true));
				i = boldEnd = close + BOLD.length;
				continue;
			}
		}
		if (text.startsWith(OPEN, i)) {
			const close = text.indexOf(CLOSE, i + OPEN.length + 1);
			if (close !== -1) {
				flush();
				spans.push({ t: text.slice(i + OPEN.length, close), b: false, p: true });
				i = close + CLOSE.length;
				continue;
			}
		}
		literal += text[i];
		i += 1;
	}
	flush();
	return spans;
}

function placeholders(text: string, bold: boolean): Span[] {
	const spans: Span[] = [];
	let start = 0;
	let i = 0;
	while (i < text.length) {
		if (text.startsWith(OPEN, i)) {
			const close = text.indexOf(CLOSE, i + OPEN.length + 1);
			if (close !== -1) {
				if (i > start) spans.push({ t: text.slice(start, i), b: bold, p: false });
				spans.push({ t: text.slice(i + OPEN.length, close), b: bold, p: true });
				i = start = close + CLOSE.length;
				continue;
			}
		}
		i += 1;
	}
	if (start < text.length) spans.push({ t: text.slice(start), b: bold, p: false });
	return spans;
}
