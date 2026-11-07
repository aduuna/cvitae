/**
 * Highlighting for the CV Markdown format (markdown.ts): heading marks, section kinds, field names,
 * bullet marks, bold and links. Placeholders are marked by the code editor itself.
 */
import { StreamLanguage, type StringStream } from '@codemirror/language';

interface State {
	/** Inside **bold** on this line. */
	bold: boolean;
	/** On a heading line. */
	heading: boolean;
}

const KIND = /^\{(?:experience|projects|education|skills|certifications|custom)\}\s*$/;

export const cvMarkdown = StreamLanguage.define<State>({
	name: 'cv-markdown',
	startState: () => ({ bold: false, heading: false }),
	token(stream: StringStream, state: State): string | null {
		if (stream.sol()) {
			state.bold = false;
			state.heading = false;
			if (stream.match(/^#{1,6}(?=\s|$)/)) {
				state.heading = true;
				return 'processingInstruction';
			}
			if (stream.match(/^\s*[-*](?=\s|$)/)) return 'processingInstruction';
			if (stream.match(/^[A-Za-z][A-Za-z ]{0,19}?(?=\s*:)/)) return 'keyword';
		}
		if (state.heading) {
			if (stream.match(KIND)) return 'meta';
			if (stream.match(/^[^{]+/) || stream.next()) return 'heading';
		}
		if (stream.match('\\')) {
			stream.next();
			return state.bold ? 'strong' : null;
		}
		if (stream.match('**')) {
			state.bold = !state.bold;
			return 'processingInstruction';
		}
		if (stream.match(/^\[(?!\[)[^\]]*\]\([^)\s]*\)/)) return 'link';
		if (!stream.match(/^[^\\*[]+/)) stream.next();
		return state.bold ? 'strong' : null;
	}
});
