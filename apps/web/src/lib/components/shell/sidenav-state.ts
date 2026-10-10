const STORAGE_KEY = 'vitae.sidenav.collapsed';

/** The user's collapse choice; storage can be unavailable (private mode), so failures fall back. */
export function loadCollapsed(): boolean {
	try {
		return localStorage.getItem(STORAGE_KEY) === 'true';
	} catch {
		return false;
	}
}

export function saveCollapsed(collapsed: boolean): void {
	try {
		localStorage.setItem(STORAGE_KEY, String(collapsed));
	} catch {
		// Not persisted; the choice still applies for this session.
	}
}
