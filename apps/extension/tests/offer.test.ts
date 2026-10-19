import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { installChrome, type FakeChrome } from './chrome.ts';
import { loadFixture, sampleData } from './helpers.ts';

/** The content script as it runs on a job site: it offers to fill when a form shows up. */
let fake: FakeChrome;
const prompt = () => document.querySelector('cvitae-prompt')?.shadowRoot ?? null;
const promptText = () => prompt()?.querySelector('.text')?.textContent ?? null;

beforeAll(async () => {
	vi.useFakeTimers({ shouldAdvanceTime: true });
	fake = installChrome();
	fake.chrome.runtime.sendMessage.mockImplementation(async (message: unknown) => {
		const { type } = message as { type: string };
		if (type === 'offer') return { show: true, source: 'Data engineering profile' };
		if (type === 'application') return { ok: true, data: sampleData() };
		return null;
	});
	await import('../src/content/index.ts');
});

beforeEach(() => vi.stubGlobal('chrome', fake.chrome));

async function settle(): Promise<void> {
	await vi.advanceTimersByTimeAsync(1000);
}

describe('the offer on job sites', () => {
	it('appears when an application form is drawn after the page loaded, and reads nothing yet', async () => {
		await settle();
		expect(prompt()).toBeNull();

		loadFixture('lever');
		await settle();

		expect(promptText()).toMatch(/^Fill this application from your Data engineering profile\?/);
		expect(fake.chrome.runtime.sendMessage).toHaveBeenCalledWith({
			type: 'offer',
			url: location.href
		});
		// The data is asked for only when the user chooses Fill fields (a trusted click; see the
		// Playwright test, as jsdom cannot make one).
		expect(fake.chrome.runtime.sendMessage).not.toHaveBeenCalledWith(
			expect.objectContaining({ type: 'application' })
		);
	});

	it('offers again on the next step of a single-page application', async () => {
		history.pushState({}, '', '/apply/step-2');
		loadFixture('workday');
		await settle();

		// The experience step has no contact fields; its roles are reason enough.
		expect(promptText()).toMatch(/^Fill this application/);
		expect(fake.chrome.runtime.sendMessage).toHaveBeenLastCalledWith({
			type: 'offer',
			url: location.href
		});
	});

	it('stays away from pages without an application form', async () => {
		history.pushState({}, '', '/about');
		document.body.innerHTML = '<form><label for="q">Search jobs</label><input id="q"></form>';
		await settle();

		expect(prompt()).toBeNull();
	});
});
