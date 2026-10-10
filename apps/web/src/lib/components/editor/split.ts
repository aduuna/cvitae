const STORAGE_KEY = 'vitae.editor.split';

/** The edit panel width the user chose last; storage can be unavailable (private mode). */
export function loadSplit(): number | null {
	try {
		const value = Number(localStorage.getItem(STORAGE_KEY));
		return Number.isFinite(value) && value > 0 ? value : null;
	} catch {
		return null;
	}
}

export function saveSplit(width: number): void {
	try {
		localStorage.setItem(STORAGE_KEY, String(Math.round(width)));
	} catch {
		// Not persisted; the width still applies for this session.
	}
}
