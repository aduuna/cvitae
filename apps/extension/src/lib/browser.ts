/**
 * The few places Chrome and Firefox differ. Both offer the promise-based `chrome` namespace in
 * Manifest V3; Firefox has a sidebar where Chrome has a side panel. The build sets VITE_TARGET,
 * so each browser's bundle holds only its own branch.
 */

interface FirefoxSidebar {
	toggle(): Promise<void>;
}

/**
 * Open the panel from a toolbar click. Must run straight from the click: Firefox refuses the
 * sidebar after an await, and Chrome refuses the side panel without a user gesture. The click
 * also gives the extension access to the page in that tab (activeTab).
 */
export function openPanel(tab: chrome.tabs.Tab): void {
	if (import.meta.env.VITE_TARGET === 'firefox') {
		const { browser } = globalThis as unknown as { browser: { sidebarAction: FirefoxSidebar } };
		void browser.sidebarAction.toggle();
	} else if (tab.windowId !== undefined) {
		void chrome.sidePanel.open({ windowId: tab.windowId });
	}
}
