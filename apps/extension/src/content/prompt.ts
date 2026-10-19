import { SHADOW_POP, tokenProperties } from './tokens.ts';

/**
 * The offer to fill an application, in the page's corner. It lives in a shadow root so the site's
 * styles cannot reach it, and it does nothing until the user chooses Fill fields: no data is
 * fetched before that. Its buttons ignore clicks a script makes, so the page cannot fill itself.
 */

export type FillOutcome = { ok: true; count: number } | { ok: false; message: string };

export interface PromptActions {
	/** Where the data comes from, for the offer: "Backend profile". */
	source: string;
	fill(): Promise<FillOutcome>;
	undo(): number;
	close(): void;
}

const STYLE = `
${tokenProperties()}
:host { all: initial; position: fixed; right: 16px; bottom: 16px; z-index: 2147483647; }
.card {
	box-sizing: border-box; width: 320px; padding: 16px; display: flex; flex-direction: column;
	gap: 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface);
	color: var(--fg); box-shadow: ${SHADOW_POP};
	font: 400 14px/20px "Geist Variable", ui-sans-serif, system-ui, sans-serif;
}
.title { margin: 0; font-size: 14px; font-weight: 600; }
.text { margin: 0; color: var(--fg-muted); font-size: 13px; line-height: 18px; }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
button {
	height: 32px; padding: 0 12px; border-radius: 6px; font: inherit; font-weight: 500;
	cursor: pointer; border: 1px solid var(--line); background: var(--surface); color: var(--fg);
}
button.primary { border-color: var(--accent); background: var(--accent); color: var(--accent-fg); }
button:disabled { opacity: 0.4; cursor: not-allowed; }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
`;

/** Show the offer; returns a function that removes it. `trusted` decides whether a click is the
 * user's (tests, whose clicks are synthetic, replace it). */
export function showPrompt(
	actions: PromptActions,
	doc: Document = document,
	trusted: (event: Event) => boolean = (event) => event.isTrusted
): () => void {
	const button = (label: string, primary: boolean, onclick: () => void) => {
		const el = doc.createElement('button');
		el.type = 'button';
		el.textContent = label;
		if (primary) el.className = 'primary';
		el.addEventListener('click', (event) => {
			if (trusted(event)) onclick();
		});
		return el;
	};
	const host = doc.createElement('cvitae-prompt');
	const root = host.attachShadow({ mode: 'open' });
	const style = doc.createElement('style');
	style.textContent = STYLE;
	const card = doc.createElement('section');
	card.className = 'card';
	card.setAttribute('aria-label', 'Chameleon vitae');
	const title = doc.createElement('p');
	title.className = 'title';
	title.textContent = 'Chameleon vitae';
	const text = doc.createElement('p');
	text.className = 'text';
	text.setAttribute('aria-live', 'polite');
	const row = doc.createElement('div');
	row.className = 'actions';
	card.append(title, text, row);
	root.append(style, card);

	const remove = () => {
		host.remove();
		actions.close();
	};

	const offer = () => {
		text.textContent = `Fill this application from your ${actions.source}? Nothing is sent until you submit it yourself.`;
		const fill = button('Fill fields', true, async () => {
			fill.disabled = true;
			const outcome = await actions.fill();
			if (outcome.ok) filled(outcome.count);
			else {
				text.textContent = outcome.message;
				fill.disabled = false;
			}
		});
		row.replaceChildren(button('Close', false, remove), fill);
	};

	const filled = (count: number) => {
		text.textContent =
			count === 0
				? 'There were no empty fields to fill. Open the extension from the toolbar to review them.'
				: `Filled ${count} ${count === 1 ? 'field' : 'fields'}. Check each one before you submit.`;
		const undo = button('Undo fill', false, () => {
			const restored = actions.undo();
			text.textContent = `Put back ${restored} ${restored === 1 ? 'field' : 'fields'}.`;
			undo.disabled = true;
		});
		row.replaceChildren(...(count > 0 ? [undo] : []), button('Close', true, remove));
	};

	offer();
	(doc.body ?? doc.documentElement).append(host);
	return () => host.remove();
}
