import { api, errorMessage, unwrap, type Schemas } from '#lib/api/client.ts';
import type { SelectOption } from '#lib/components/ui/Select.svelte';
import type { AiModel, CvContent, FactIssue } from '#lib/cv/types.ts';

export type ChatTurn = Schemas['ChatTurn'];

/** The scope for the whole CV in the part picker; the api takes null. */
export const WHOLE_CV = '';

/** How many earlier messages go with a request, as context (the api takes at most 12). */
const HISTORY = 12;

/** What an edit did to the form. */
export interface AppliedEdit {
	/** The form content before the edit, for undo. */
	before: CvContent;
	after: CvContent;
	/** `stale`: the form changed while the request ran, so the edit waits to be applied. */
	status: 'applied' | 'stale' | 'undone';
}

export type ChatMessage =
	| { id: number; role: 'user'; text: string; scope: string | null }
	| {
			id: number;
			role: 'assistant';
			text: string;
			issues: FactIssue[];
			model: AiModel;
			edit: AppliedEdit | null;
	  }
	| { id: number; role: 'error'; text: string };

/** The editor the chat works on. */
export interface ChatEditor {
	/** The content in the form now. */
	content: () => CvContent;
	/** Saves pending form edits, so the AI works on what the user sees. */
	save: () => Promise<void>;
	/** Puts content into the form, where autosave saves it. */
	apply: (content: CvContent) => void;
}

/** The parts of a CV a request can be limited to: the whole CV, the summary or one section. */
export function scopeOptions(content: CvContent): SelectOption[] {
	return [
		{ value: WHOLE_CV, label: 'Whole CV' },
		{ value: 'summary', label: 'Summary' },
		...content.sections.map((section) => ({
			value: section.id,
			label: section.title.trim() || 'Untitled section'
		}))
	];
}

/** The latest user and assistant messages, oldest first, as the api's conversation. */
export function historyOf(messages: ChatMessage[]): ChatTurn[] {
	const turns: ChatTurn[] = [];
	for (const message of messages) {
		if (message.role !== 'error') turns.push({ role: message.role, text: message.text });
	}
	return turns.slice(-HISTORY);
}

export function sameContent(a: CvContent, b: CvContent): boolean {
	return JSON.stringify(a) === JSON.stringify(b);
}

/** A plain copy, detached from the form's reactive state. */
function copy(content: CvContent): CvContent {
	return $state.snapshot(content) as CvContent;
}

/** A conversation with the AI about one CV. Each request is one AI run. */
export class AiEditChat {
	messages = $state<ChatMessage[]>([]);
	pending = $state(false);

	readonly #documentId: string;
	readonly #editor: ChatEditor;
	#controller: AbortController | null = null;
	#next = 0;

	constructor(documentId: string, editor: ChatEditor) {
		this.#documentId = documentId;
		this.#editor = editor;
	}

	/**
	 * Asks for `text`, limited to `scope` (a section id or "summary"; null for the whole CV). An edit
	 * goes into the form at once unless the form changed while it ran. Resolves false when the
	 * request failed or was stopped, so the caller can give the text back.
	 */
	async send(text: string, options: { scope: string | null; model: AiModel | null }) {
		const message = text.trim();
		if (!message || this.pending) return false;
		const history = historyOf(this.messages);
		this.messages.push({ id: this.#next++, role: 'user', text: message, scope: options.scope });
		this.pending = true;
		const controller = (this.#controller = new AbortController());
		try {
			await this.#editor.save();
			const before = copy(this.#editor.content());
			const result = await unwrap(
				api.POST('/api/v1/documents/{document_id}/ai-edit', {
					params: { path: { document_id: this.#documentId } },
					body: { message, scope: options.scope, history, ai_model: options.model },
					signal: controller.signal
				})
			);
			let edit: AppliedEdit | null = null;
			if (result.changed) {
				const stale = !sameContent(this.#editor.content(), before);
				if (!stale) this.#editor.apply(copy(result.content));
				edit = { before, after: result.content, status: stale ? 'stale' : 'applied' };
			}
			this.messages.push({
				id: this.#next++,
				role: 'assistant',
				text: result.reply || (result.changed ? 'Done.' : 'I made no change.'),
				issues: result.issues,
				model: result.ai_model,
				edit
			});
			return true;
		} catch (error) {
			const stopped = error instanceof DOMException && error.name === 'AbortError';
			this.messages.push({
				id: this.#next++,
				role: 'error',
				text: stopped ? 'Stopped. Nothing was changed.' : errorMessage(error)
			});
			return false;
		} finally {
			this.pending = false;
			if (this.#controller === controller) this.#controller = null;
		}
	}

	stop(): void {
		this.#controller?.abort();
	}

	/** The latest edit in the form can be undone while the form still holds what it made. */
	canUndo(message: ChatMessage): boolean {
		if (message.role !== 'assistant' || message.edit?.status !== 'applied') return false;
		const latest = this.messages.findLast(
			(other) => other.role === 'assistant' && other.edit?.status === 'applied'
		);
		return latest === message && sameContent(this.#editor.content(), message.edit.after);
	}

	undo(message: ChatMessage): void {
		if (!this.canUndo(message) || message.role !== 'assistant' || !message.edit) return;
		this.#editor.apply(copy(message.edit.before));
		message.edit.status = 'undone';
	}

	/** An edit that waited because the form changed while it ran, while it is the latest reply. */
	canApply(message: ChatMessage): boolean {
		if (message.role !== 'assistant' || message.edit?.status !== 'stale') return false;
		return this.messages.findLast((other) => other.role === 'assistant') === message;
	}

	applyAnyway(message: ChatMessage): void {
		if (!this.canApply(message) || message.role !== 'assistant' || !message.edit) return;
		message.edit.before = copy(this.#editor.content());
		this.#editor.apply(copy(message.edit.after));
		message.edit.status = 'applied';
	}

	dispose(): void {
		this.stop();
	}
}
