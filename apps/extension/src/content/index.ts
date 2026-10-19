import { send } from '../lib/messages.ts';
import { controlCount, element, scan } from './fields.ts';
import { attachFile, fillFields, undoFill } from './fill.ts';
import { readJob } from './job.ts';
import { looksLikeApplication, planFill } from './plan.ts';
import { showPrompt, type FillOutcome } from './prompt.ts';

const CHECK_DELAY_MS = 800;

/** Fill every empty field the data answers, as the prompt's Fill fields does. */
async function fillFromPrompt(): Promise<FillOutcome> {
	const reply = await send('application', { url: location.href }).catch(() => null);
	if (!reply) return { ok: false, message: 'The extension did not answer. Reload the page.' };
	if (!reply.ok) return reply;
	const plan = planFill(scan(document).fields, reply.data);
	return {
		ok: true,
		count: fillFields(
			plan.assignments.filter((a) => a.include),
			element
		)
	};
}

/**
 * Offer to fill when an application form shows up, once per address: single-page sites like
 * Workday change the address for each step and draw the form after the page loads.
 */
function watchForForms(): void {
	let checkedOn: string | null = null;
	let offeredOn: string | null = null;
	let controls = -1;
	let removePrompt: (() => void) | null = null;
	let timer: ReturnType<typeof setTimeout> | undefined;

	const check = async () => {
		const href = location.href;
		if (href !== checkedOn) {
			// A new step: count its controls afresh, and drop the offer made for the last one.
			checkedOn = href;
			controls = -1;
			removePrompt?.();
			removePrompt = null;
		}
		const count = controlCount(document);
		if (removePrompt || offeredOn === href || count === controls) return;
		controls = count;
		if (!looksLikeApplication(scan(document))) return;
		offeredOn = href;
		const offer = await send('offer', { url: href }).catch(() => null);
		if (!offer?.show || location.href !== href) return;
		removePrompt = showPrompt({
			source: offer.source,
			fill: fillFromPrompt,
			undo: undoFill,
			close: () => (removePrompt = null)
		});
	};
	const later = () => {
		clearTimeout(timer);
		timer = setTimeout(() => void check(), CHECK_DELAY_MS);
	};
	new MutationObserver(later).observe(document.documentElement, { childList: true, subtree: true });
	later();
}

// Injected again when the side panel scans a page: keep the first copy.
if (!globalThis.__cvitae) {
	globalThis.__cvitae = {
		scan: () => scan(document),
		fill: (assignments) => fillFields(assignments, element),
		undo: undoFill,
		attach: (fieldId, file) => attachFile(element(fieldId), file),
		job: () => readJob(document)
	};
	if (!globalThis.__cvitaeQuiet) watchForForms();
}
