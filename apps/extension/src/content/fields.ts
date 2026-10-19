import { classify, isRepeated, words, type Described } from './classify.ts';
import type { FieldInfo, FileField, PageScan } from './types.ts';

type Control = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

const CONTROLS = 'input, textarea, select';
const HEADINGS = 'h1, h2, h3, h4, h5, h6, legend, [role="heading"]';
const MAX_FIELDS = 400;
const MAX_OPTIONS = 400;
/** Attributes that sites put on fields and their wrappers to name them (Workday, Lever, tests). */
const NAMING_ATTRIBUTES = ['data-automation-id', 'data-qa', 'data-testid', 'data-field', 'data-ui'];

/**
 * Each element keeps its id for as long as it exists, so a scan made while the user reviews an
 * earlier one (the page changed, the prompt looked again) cannot point a fill at another field.
 */
const ids = new WeakMap<Element, string>();
const elements = new Map<string, WeakRef<Element>>();
let lastId = 0;

function idFor(el: Element, prefix: 'f' | 'u'): string {
	let id = ids.get(el);
	if (!id) {
		id = `${prefix}${++lastId}`;
		ids.set(el, id);
		elements.set(id, new WeakRef(el));
	}
	return id;
}

export function element(id: string): Element | undefined {
	return elements.get(id)?.deref();
}

/** Controls in page order, including those inside open shadow roots. */
function controls(root: Document | ShadowRoot, out: Control[] = []): Control[] {
	for (const el of root.querySelectorAll('*')) {
		if (el.matches(CONTROLS)) out.push(el as Control);
		if (el.shadowRoot) controls(el.shadowRoot, out);
	}
	return out;
}

/** Smaller than this, in both directions, a text field is not one a person types in. */
const MIN_SIZE = 4;

/**
 * Whether the user can see the field. A text field must be in sight too: transparent, tiny or off
 * the page, it is not one the user fills, and a page could hide such fields to collect more than it
 * shows. Checkboxes and lists only need to be displayed: sites often hide them behind their own
 * styled controls, which follow the hidden one.
 */
function visible(el: Control): boolean {
	if (el.closest('[hidden], [inert], [aria-hidden="true"]')) return false;
	// jsdom has no layout; there everything counts as visible.
	if (typeof el.checkVisibility !== 'function') return true;
	const styled = el instanceof HTMLSelectElement || el.type === 'checkbox';
	if (!el.checkVisibility({ checkVisibilityCSS: true, checkOpacity: !styled })) return false;
	if (styled) return true;
	const box = el.getBoundingClientRect();
	const offPage = box.right + window.scrollX <= 0 || box.bottom + window.scrollY <= 0;
	return box.width >= MIN_SIZE && box.height >= MIN_SIZE && !offPage;
}

const SKIP_TEXT = new Set(['SELECT', 'TEXTAREA', 'OPTION', 'SCRIPT', 'STYLE', 'BUTTON', 'svg']);
/** Elements that end a run of text, so their words do not run into the next ones. */
const BLOCKS = /^(DIV|P|LI|BR|H\d)$/;

/** The text a reader sees in `el`, without the options of a list or a button's label inside it. */
export function ownText(el: Element): string {
	let text = '';
	const walk = (node: Node) => {
		for (const child of node.childNodes) {
			if (child.nodeType === Node.TEXT_NODE) text += child.textContent ?? '';
			else if (child instanceof Element && !SKIP_TEXT.has(child.tagName)) {
				walk(child);
				if (BLOCKS.test(child.tagName)) text += ' ';
			}
		}
	};
	walk(el);
	return text;
}

/** A label's text without required markers: "First name *" reads "First name". */
export function cleanLabel(text: string): string {
	return text
		.replace(/[*\u2731\u2022]/g, ' ')
		.replace(/\((required|optional)\)/gi, ' ')
		.replace(/\s+/g, ' ')
		.replace(/\s*:\s*$/, '')
		.trim()
		.slice(0, 150);
}

function byIds(el: Element, attribute: string): string {
	const ids = el.getAttribute(attribute)?.split(/\s+/).filter(Boolean) ?? [];
	const root = el.getRootNode() as Document | ShadowRoot;
	return ids
		.map((id) => root.getElementById?.(id) ?? el.ownerDocument.getElementById(id))
		.map((node) => (node ? ownText(node) : ''))
		.join(' ');
}

const SHORT_LABEL = 100;

/** Text just before the field in its wrappers, as in Lever's "application-label" divs. */
function nearbyText(el: Element): string {
	let node: Element | null = el;
	for (let depth = 0; depth < 4 && node?.parentElement; depth++) {
		let sibling = node.previousElementSibling;
		for (let tries = 0; sibling && tries < 2; tries++) {
			// A heading names the section, not the field; another field's label is not this one's.
			if (sibling.matches(HEADINGS)) return '';
			const forOther = sibling.matches('label[for]') && sibling.getAttribute('for') !== el.id;
			if (!forOther && !sibling.querySelector(CONTROLS) && !sibling.matches(CONTROLS)) {
				const text = cleanLabel(ownText(sibling));
				if (text && text.length <= SHORT_LABEL) return text;
			}
			sibling = sibling.previousElementSibling;
		}
		node = node.parentElement;
		if (node.querySelectorAll(CONTROLS).length > 3) break;
	}
	return '';
}

export function labelOf(el: Control): string {
	const labels = 'labels' in el && el.labels ? [...el.labels] : [];
	const candidates = [
		labels.map((label) => ownText(label)).join(' '),
		byIds(el, 'aria-labelledby'),
		el.getAttribute('aria-label') ?? '',
		nearbyText(el),
		el.getAttribute('placeholder') ?? '',
		el.getAttribute('title') ?? ''
	];
	for (const candidate of candidates) {
		const text = cleanLabel(candidate);
		if (text) return text;
	}
	return '';
}

/** The heading of the section the field sits in, looking no further than its form. */
export function contextOf(el: Element): string {
	const form = el.closest('form');
	let node = el.parentElement;
	for (let depth = 0; node && depth < 12; depth++) {
		if (node.tagName === 'FIELDSET') {
			const legend = node.querySelector(':scope > legend');
			if (legend) return cleanLabel(ownText(legend));
		}
		const role = node.getAttribute('role');
		if (role === 'group' || role === 'region') {
			const named = byIds(node, 'aria-labelledby') || node.getAttribute('aria-label') || '';
			if (named.trim()) return cleanLabel(named);
		}
		let last: Element | null = null;
		for (const heading of node.querySelectorAll(HEADINGS)) {
			const before = heading.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING;
			if (before && !heading.contains(el)) last = heading;
		}
		if (last) return cleanLabel(ownText(last));
		if (node === form) break;
		node = node.parentElement;
	}
	return '';
}

function hintsOf(el: Control): string[] {
	const hints = [el.getAttribute('name') ?? '', el.id];
	let node: Element | null = el;
	for (let depth = 0; node && depth < 5; depth++) {
		for (const attribute of NAMING_ATTRIBUTES) hints.push(node.getAttribute(attribute) ?? '');
		node = node.parentElement;
	}
	return [...new Set(hints.filter(Boolean))];
}

const PLACEHOLDER_OPTION = /^(select|choose|please|pick|--|-|none selected)\b|^$/i;

function isFilled(el: Control): boolean {
	if (el instanceof HTMLSelectElement) {
		const option = el.selectedOptions[0];
		return Boolean(option && el.value !== '' && !PLACEHOLDER_OPTION.test(option.text.trim()));
	}
	if (el instanceof HTMLInputElement && el.type === 'checkbox') return el.checked;
	return el.value.trim() !== '';
}

function describe(el: Control): Described {
	const tag = el.tagName.toLowerCase() as Described['tag'];
	const options =
		el instanceof HTMLSelectElement
			? [...el.options]
					.slice(0, MAX_OPTIONS)
					.map((option) => ({ value: option.value, text: option.text.trim() }))
			: null;
	const maxLength = 'maxLength' in el && el.maxLength > 0 ? el.maxLength : null;
	return {
		tag,
		type: el instanceof HTMLInputElement ? el.type : tag,
		label: labelOf(el),
		context: contextOf(el),
		hints: hintsOf(el),
		autocomplete: el.getAttribute('autocomplete') ?? '',
		placeholder: el.getAttribute('placeholder') ?? '',
		maxLength,
		options,
		filled: isFilled(el),
		needsChoice:
			el.getAttribute('role') === 'combobox' ||
			/^(list|both)$/.test(el.getAttribute('aria-autocomplete') ?? '') ||
			el.hasAttribute('list') ||
			el.getAttribute('aria-haspopup') === 'listbox'
	};
}

const CV_FILE = /\b(resume|cv|curriculum vitae|curriculum)\b/;

function fileField(el: HTMLInputElement): Omit<FileField, 'id'> | null {
	const text = words([labelOf(el), ...hintsOf(el), el.getAttribute('accept') ?? ''].join(' '));
	if (!CV_FILE.test(text) || /\bcover\b/.test(text)) return null;
	return { label: labelOf(el) || 'CV', hasFile: (el.files?.length ?? 0) > 0 };
}

/** Every field the profile can fill, and the file inputs that take a CV. */
export function scan(doc: Document = document): PageScan {
	const fields: FieldInfo[] = [];
	const files: FileField[] = [];
	const counts = new Map<string, number>();
	for (const el of controls(doc)) {
		if (el instanceof HTMLInputElement && el.type === 'file') {
			const file = fileField(el);
			if (file) files.push({ ...file, id: idFor(el, 'u') });
			continue;
		}
		if (fields.length >= MAX_FIELDS || el.disabled || ('readOnly' in el && el.readOnly)) continue;
		if (!visible(el)) continue;
		const described = describe(el);
		const classified = classify(described);
		if (!classified) continue;
		const key = `${classified.kind}:${classified.part ?? ''}`;
		const group = isRepeated(classified.kind) ? (counts.get(key) ?? 0) : 0;
		counts.set(key, group + 1);
		fields.push({ ...described, ...classified, group, id: idFor(el, 'f') });
	}
	return { url: doc.location?.href ?? '', title: doc.title, fields, files };
}

/** How many controls the page has: a cheap check for whether a form appeared. */
export function controlCount(doc: Document = document): number {
	return doc.querySelectorAll(CONTROLS).length;
}
