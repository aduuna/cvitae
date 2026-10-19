import type { JobDraft, PageScan } from '../content/types.ts';
import type { CvFile } from './api.ts';

/**
 * The side panel's view of the page in the active tab. Everything runs through
 * scripting.executeScript, in every frame the extension may read: application forms are often in
 * an iframe (a Greenhouse form embedded on a company's careers page).
 */

export interface FrameScan {
	frameId: number;
	scan: PageScan;
}

export async function activeTab(): Promise<chrome.tabs.Tab | null> {
	const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
	return tab ?? null;
}

/** Load the content script into the tab's frames. False when the extension may not read the page. */
export async function prepare(tabId: number): Promise<boolean> {
	try {
		await chrome.scripting.executeScript({
			target: { tabId, allFrames: true },
			func: () => {
				globalThis.__cvitaeQuiet = true;
			}
		});
		await chrome.scripting.executeScript({
			target: { tabId, allFrames: true },
			files: ['content.js']
		});
		return true;
	} catch {
		return false;
	}
}

export async function scanTab(tabId: number): Promise<FrameScan[]> {
	const results = await chrome.scripting.executeScript({
		target: { tabId, allFrames: true },
		func: () => globalThis.__cvitae?.scan() ?? null
	});
	return results.flatMap(({ frameId, result }) =>
		result ? [{ frameId, scan: result as PageScan }] : []
	);
}

export async function fillFrame(
	tabId: number,
	frameId: number,
	assignments: { fieldId: string; value: string }[]
): Promise<number> {
	const [result] = await chrome.scripting.executeScript({
		target: { tabId, frameIds: [frameId] },
		func: (list: { fieldId: string; value: string }[]) => globalThis.__cvitae?.fill(list) ?? 0,
		args: [assignments]
	});
	return (result?.result as number | undefined) ?? 0;
}

export async function undoTab(tabId: number): Promise<number> {
	const results = await chrome.scripting.executeScript({
		target: { tabId, allFrames: true },
		func: () => globalThis.__cvitae?.undo() ?? 0
	});
	return results.reduce((sum, { result }) => sum + ((result as number | undefined) ?? 0), 0);
}

export async function attachInFrame(
	tabId: number,
	frameId: number,
	fieldId: string,
	file: CvFile
): Promise<boolean> {
	const [result] = await chrome.scripting.executeScript({
		target: { tabId, frameIds: [frameId] },
		func: (id: string, cv: CvFile) => globalThis.__cvitae?.attach(id, cv) ?? false,
		args: [fieldId, file]
	});
	return result?.result === true;
}

/** The job ad: from the top page first, else from a frame that has one. */
export async function readJobFromTab(tabId: number): Promise<JobDraft | null> {
	const results = await chrome.scripting.executeScript({
		target: { tabId, allFrames: true },
		func: () => globalThis.__cvitae?.job() ?? null
	});
	const drafts = results
		.filter(({ result }) => result)
		.sort((a, b) => (a.frameId === 0 ? -1 : b.frameId === 0 ? 1 : 0))
		.map(({ result }) => result as JobDraft);
	return drafts.find((draft) => draft.from === 'posting') ?? drafts[0] ?? null;
}

export function hostOf(href: string): string | null {
	try {
		return new URL(href).hostname || null;
	} catch {
		return null;
	}
}

/** The pattern for a site, for asking to read it. */
export function sitePattern(href: string): string | null {
	try {
		const url = new URL(href);
		return /^https?:$/.test(url.protocol) ? `${url.protocol}//${url.hostname}/*` : null;
	} catch {
		return null;
	}
}

/**
 * Ask to read a site from now on, and offer filling there as on known job sites. Call it straight
 * from a click: browsers only show the request for a user's action.
 */
export function allowSite(pattern: string): Promise<boolean> {
	return chrome.permissions.request({ origins: [pattern] }).then(async (granted) => {
		if (granted) {
			await chrome.scripting
				.registerContentScripts([
					{
						id: `site-${pattern}`,
						matches: [pattern],
						js: ['content.js'],
						runAt: 'document_idle',
						allFrames: true,
						persistAcrossSessions: true
					}
				])
				.catch(() => {});
		}
		return granted;
	});
}

export function canRead(pattern: string): Promise<boolean> {
	return chrome.permissions.contains({ origins: [pattern] });
}
