import { FILLED_STYLE } from './tokens.ts';

type Control = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

const FILLED = 'data-cvitae-filled';

/** What a fill changed, so it can be undone. */
const history: { el: Control; value: string; checked: boolean }[] = [];

/**
 * Set a value the way typing does, so frameworks that track input (React, Vue, Angular) see it.
 * React keeps its own copy of the value on the element: the prototype's setter goes around it.
 */
function setValue(el: Control, value: string): void {
	const proto =
		el instanceof HTMLSelectElement
			? HTMLSelectElement.prototype
			: el instanceof HTMLTextAreaElement
				? HTMLTextAreaElement.prototype
				: HTMLInputElement.prototype;
	const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
	if (setter) setter.call(el, value);
	else el.value = value;
}

/** Write one field: focus, the value, the events a user's typing makes, then blur. */
export function write(el: Control, value: string): void {
	el.dispatchEvent(new FocusEvent('focus'));
	el.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
	if (el instanceof HTMLInputElement && el.type === 'checkbox') {
		// A click toggles it and fires what a user's click does; frameworks listen for that.
		if (el.checked !== (value === 'true')) el.click();
	} else {
		setValue(el, value);
		el.dispatchEvent(
			new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value })
		);
		el.dispatchEvent(new Event('change', { bubbles: true }));
	}
	el.dispatchEvent(new FocusEvent('focusout', { bubbles: true }));
	el.dispatchEvent(new FocusEvent('blur'));
}

function ensureStyle(doc: Document): void {
	if (doc.getElementById('cvitae-filled-style')) return;
	const style = doc.createElement('style');
	style.id = 'cvitae-filled-style';
	style.textContent = `[${FILLED}] { ${FILLED_STYLE} }`;
	(doc.head ?? doc.documentElement).append(style);
}

/** Mark a filled field until the user changes it, so they can see what to check. */
function mark(el: Control): void {
	ensureStyle(el.ownerDocument);
	el.setAttribute(FILLED, '');
	const clear = () => el.removeAttribute(FILLED);
	el.addEventListener('keydown', clear, { once: true });
	el.addEventListener('pointerdown', clear, { once: true });
}

/** Fill fields found by `lookup`; returns how many were written. A new fill replaces the undo. */
export function fillFields(
	assignments: { fieldId: string; value: string }[],
	lookup: (id: string) => Element | undefined
): number {
	history.length = 0;
	let count = 0;
	for (const { fieldId, value } of assignments) {
		const el = lookup(fieldId);
		if (
			!(
				el instanceof HTMLInputElement ||
				el instanceof HTMLTextAreaElement ||
				el instanceof HTMLSelectElement
			) ||
			!el.isConnected
		) {
			continue;
		}
		history.push({ el, value: el.value, checked: 'checked' in el ? el.checked : false });
		write(el, value);
		mark(el);
		count += 1;
	}
	return count;
}

/** Put back what the last fill replaced; returns how many fields changed back. */
export function undoFill(): number {
	let count = 0;
	for (const { el, value, checked } of history.reverse()) {
		if (!el.isConnected) continue;
		write(el, el instanceof HTMLInputElement && el.type === 'checkbox' ? String(checked) : value);
		el.removeAttribute(FILLED);
		count += 1;
	}
	history.length = 0;
	return count;
}

/** Put a file in a file input, as choosing it in the file picker does. */
export function attachFile(
	el: Element | undefined,
	file: { name: string; type: string; base64: string }
): boolean {
	if (!(el instanceof HTMLInputElement) || el.type !== 'file') return false;
	const bytes = Uint8Array.from(atob(file.base64), (char) => char.charCodeAt(0));
	const transfer = new DataTransfer();
	transfer.items.add(new File([bytes], file.name, { type: file.type }));
	el.files = transfer.files;
	el.dispatchEvent(new Event('input', { bubbles: true }));
	el.dispatchEvent(new Event('change', { bubbles: true }));
	return true;
}
