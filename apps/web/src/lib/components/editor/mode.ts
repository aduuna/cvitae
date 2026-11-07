export type EditMode = 'form' | 'markdown' | 'typst';

const STORAGE_KEY = 'vitae.editor.mode';
const MODES: readonly string[] = ['form', 'markdown', 'typst'];

/** The editing mode the user chose last; Form when there is none or storage is unavailable. */
export function loadMode(): EditMode {
	try {
		const value = localStorage.getItem(STORAGE_KEY) ?? '';
		return MODES.includes(value) ? (value as EditMode) : 'form';
	} catch {
		return 'form';
	}
}

export function saveMode(mode: EditMode): void {
	try {
		localStorage.setItem(STORAGE_KEY, mode);
	} catch {
		// Not persisted; the mode still applies for this session.
	}
}
