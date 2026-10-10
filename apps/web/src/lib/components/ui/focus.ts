const FOCUSABLE = [
	'a[href]',
	'button:not([disabled])',
	'input:not([disabled])',
	'select:not([disabled])',
	'textarea:not([disabled])',
	'[tabindex]:not([tabindex="-1"])'
].join(',');

/** Keyboard-focusable elements inside root, in DOM order. */
export function focusable(root: HTMLElement): HTMLElement[] {
	return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
		(el) => !el.closest('[inert]')
	);
}

/** Keep Tab and Shift+Tab focus cycling inside root. Call from a keydown handler. */
export function trapTab(event: KeyboardEvent, root: HTMLElement): void {
	if (event.key !== 'Tab') return;
	const items = focusable(root);
	const first = items[0];
	const last = items.at(-1);
	if (!first || !last) {
		event.preventDefault();
		root.focus();
		return;
	}
	const active = document.activeElement;
	const outside = !root.contains(active);
	if (event.shiftKey && (active === first || active === root || outside)) {
		event.preventDefault();
		last.focus();
	} else if (!event.shiftKey && (active === last || outside)) {
		event.preventDefault();
		first.focus();
	}
}
