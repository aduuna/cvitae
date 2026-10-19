import { errorMessage } from '@web/api/client.ts';
import { CONNECT_PATH } from '@web/extension/protocol.ts';
import { APP_URL } from '../config.ts';
import type { ApplicationData, FileField, JobDraft } from '../content/types.ts';
import {
	connectApi,
	disconnect,
	isRevoked,
	loadApplication,
	loadCvPdf,
	loadSession,
	saveJob,
	type Api,
	type ExtensionSession,
	type SavedJob
} from '../lib/api.ts';
import {
	activeTab,
	allowSite,
	attachInFrame,
	canRead,
	fillFrame,
	hostOf,
	prepare,
	readJobFromTab,
	scanTab,
	sitePattern,
	undoTab
} from '../lib/page.ts';
import {
	DEFAULTS,
	forgetConnection,
	loadSettings,
	onSettingsChanged,
	saveSettings,
	type Settings,
	type SourceRef
} from '../lib/settings.ts';
import { sourceName, suggestSource, type Suggestion } from '../lib/sources.ts';
import { jobSite } from '../sites.ts';
import { byFrame, review, type Row } from './review.ts';

export type FillState =
	| { step: 'idle' }
	| { step: 'scanning' }
	| { step: 'review'; rows: Row[]; notes: string[] }
	| { step: 'filling' }
	| { step: 'done'; count: number; notes: string[] }
	| { step: 'empty' }
	| { step: 'error'; message: string };

export type JobState =
	| { step: 'idle' }
	| { step: 'reading' }
	| { step: 'draft'; draft: JobDraft }
	| { step: 'saving'; draft: JobDraft }
	| { step: 'saved'; saved: SavedJob }
	| { step: 'error'; message: string };

export type AttachState =
	| { step: 'idle' }
	| { step: 'working' }
	| { step: 'attached'; name: string }
	| { step: 'placeholders'; count: number }
	| { step: 'error'; message: string };

/** Pages no extension may read: the browser's own and its extension stores. */
const UNREADABLE =
	/^https:\/\/(chromewebstore\.google\.com|chrome\.google\.com\/webstore|addons\.mozilla\.org)\//;

/**
 * Profiles, CVs and jobs older than this are loaded again when the tab changes: the user may have
 * tailored a CV in the app and come back to the application.
 */
const SESSION_TTL_MS = 30_000;

/** Everything the side panel shows, and what its buttons do. */
export class Panel {
	status = $state<'loading' | 'disconnected' | 'connected' | 'offline'>('loading');
	problem = $state<string | null>(null);
	settings = $state<Settings>({ ...DEFAULTS });
	session = $state<ExtensionSession | null>(null);
	source = $state<SourceRef | null>(null);
	reason = $state<Suggestion['reason'] | null>(null);
	pageJob = $state<Suggestion['job']>(null);
	tab = $state<{ id: number; url: string | null } | null>(null);
	/** yes: the extension can read this tab now; no: the toolbar button would give it access. */
	access = $state<'checking' | 'yes' | 'no' | 'unsupported'>('checking');
	/** Whether the site is readable without the toolbar button, so the fill offer appears there. */
	siteAllowed = $state(false);
	fill = $state<FillState>({ step: 'idle' });
	files = $state<{ frameId: number; field: FileField }[]>([]);
	attach = $state<AttachState>({ step: 'idle' });
	job = $state<JobState>({ step: 'idle' });
	details = $state<ApplicationData | null>(null);

	#api: Api | null = null;
	#data: { key: string; data: ApplicationData } | null = null;
	/** A source the user picked on this page; it wins over the suggestion until the page changes. */
	#picked: { url: string | null; source: SourceRef } | null = null;
	#loadedAt = 0;

	get site(): string | null {
		return this.tab?.url ? jobSite(this.tab.url) : null;
	}

	get host(): string | null {
		return this.tab?.url ? hostOf(this.tab.url) : null;
	}

	get sourceLabel(): string {
		return this.session && this.source ? sourceName(this.session, this.source) : '';
	}

	async start(): Promise<void> {
		onSettingsChanged(() => void this.#settingsChanged());
		chrome.tabs.onActivated.addListener(() => void this.#tabChanged());
		chrome.tabs.onUpdated.addListener((tabId, info) => {
			if (tabId === this.tab?.id && (info.status === 'complete' || info.url)) {
				void this.#tabChanged();
			}
		});
		await this.#settingsChanged();
	}

	async #settingsChanged(): Promise<void> {
		const before = this.settings.token;
		this.settings = await loadSettings();
		if (this.status !== 'loading' && before === this.settings.token) return;
		await this.reload();
	}

	/** Load the account's profiles and CVs, then look at the page. */
	async reload(): Promise<void> {
		const { token } = this.settings;
		this.#data = null;
		this.details = null;
		if (!token) {
			this.#api = null;
			this.session = null;
			this.status = 'disconnected';
			return;
		}
		this.#api = connectApi(token);
		try {
			await this.#loadSession(this.#api);
			this.status = 'connected';
			this.problem = null;
		} catch (error) {
			if (isRevoked(error)) {
				await forgetConnection();
				return;
			}
			this.status = 'offline';
			this.problem = errorMessage(error);
			return;
		}
		await this.#tabChanged();
	}

	async #loadSession(api: Api): Promise<void> {
		this.session = await loadSession(api);
		this.#loadedAt = Date.now();
	}

	async #tabChanged(): Promise<void> {
		if (this.#api && Date.now() - this.#loadedAt > SESSION_TTL_MS) {
			// Keep the list there is if this fails; a revoked token disconnects the panel.
			await this.#loadSession(this.#api).catch((error) => this.#failure(error));
		}
		this.fill = { step: 'idle' };
		this.job = { step: 'idle' };
		this.attach = { step: 'idle' };
		this.files = [];
		const tab = await activeTab();
		const url = tab?.url ?? null;
		this.tab = tab?.id === undefined ? null : { id: tab.id, url };
		if (!url) this.access = 'no';
		else if (!/^https?:/.test(url) || UNREADABLE.test(url)) this.access = 'unsupported';
		else this.access = 'yes';
		const pattern = url ? sitePattern(url) : null;
		this.siteAllowed = pattern ? await canRead(pattern).catch(() => false) : false;
		this.#suggest();
	}

	#suggest(): void {
		if (!this.session) return;
		const url = this.tab?.url ?? null;
		if (this.#picked && this.#picked.url !== url) this.#picked = null;
		const suggestion = suggestSource(this.session, [url ?? undefined], this.settings.source);
		this.pageJob = suggestion?.job ?? null;
		if (this.#picked) {
			this.source = this.#picked.source;
			this.reason = 'chosen';
		} else {
			this.source = suggestion?.source ?? null;
			this.reason = suggestion?.reason ?? null;
		}
	}

	async chooseSource(source: SourceRef): Promise<void> {
		this.#picked = { url: this.tab?.url ?? null, source };
		this.source = source;
		this.reason = 'chosen';
		this.fill = { step: 'idle' };
		this.attach = { step: 'idle' };
		this.details = null;
		await saveSettings({ source });
	}

	async #application(): Promise<ApplicationData> {
		if (!this.#api || !this.source) throw new Error('No source');
		const key = `${this.source.kind}:${this.source.id}`;
		if (this.#data?.key !== key) {
			this.#data = { key, data: await loadApplication(this.#api, this.source) };
		}
		return this.#data.data;
	}

	/** Read the form, then show what would go where. */
	async scanForm(): Promise<void> {
		const tab = this.tab;
		if (!tab) return;
		this.fill = { step: 'scanning' };
		try {
			if (!(await prepare(tab.id))) {
				this.access = 'no';
				this.fill = { step: 'idle' };
				return;
			}
			const [frames, data] = await Promise.all([scanTab(tab.id), this.#application()]);
			this.details = data;
			this.files = frames.flatMap(({ frameId, scan }) =>
				scan.files.map((field) => ({ frameId, field }))
			);
			const { rows, notes } = review(frames, data, this.sourceLabel);
			this.fill = rows.length ? { step: 'review', rows, notes } : { step: 'empty' };
		} catch (error) {
			this.fill = { step: 'error', message: await this.#failure(error) };
		}
	}

	/** Write the ticked rows into the page. */
	async confirmFill(): Promise<void> {
		const tab = this.tab;
		if (!tab || this.fill.step !== 'review') return;
		const { rows, notes } = this.fill;
		this.fill = { step: 'filling' };
		try {
			let count = 0;
			for (const [frameId, list] of byFrame(rows)) {
				count += await fillFrame(tab.id, frameId, list);
			}
			this.fill = { step: 'done', count, notes };
		} catch (error) {
			this.fill = { step: 'error', message: await this.#failure(error) };
		}
	}

	async undo(): Promise<number> {
		const restored = this.tab ? await undoTab(this.tab.id).catch(() => 0) : 0;
		this.fill = { step: 'idle' };
		return restored;
	}

	/** Attach the chosen CV, as a PDF, to the form's CV upload. */
	async attachCv(target: { frameId: number; field: FileField }): Promise<void> {
		if (!this.tab || !this.#api || this.source?.kind !== 'document') return;
		this.attach = { step: 'working' };
		try {
			const pdf = await loadCvPdf(this.#api, this.source.id);
			if (!pdf.ok) {
				this.attach = { step: 'placeholders', count: pdf.placeholders };
				return;
			}
			const done = await attachInFrame(this.tab.id, target.frameId, target.field.id, pdf.file);
			this.attach = done
				? { step: 'attached', name: pdf.file.name }
				: { step: 'error', message: 'The upload field is gone. Fill the form again.' };
		} catch (error) {
			this.attach = { step: 'error', message: await this.#failure(error) };
		}
	}

	async readJob(): Promise<void> {
		const tab = this.tab;
		if (!tab) return;
		this.job = { step: 'reading' };
		try {
			const draft = (await prepare(tab.id)) ? await readJobFromTab(tab.id) : null;
			this.job = draft
				? { step: 'draft', draft }
				: { step: 'error', message: 'There is no job ad on this page to save.' };
		} catch (error) {
			this.job = { step: 'error', message: await this.#failure(error) };
		}
	}

	async saveJob(draft: JobDraft): Promise<void> {
		if (!this.#api) return;
		this.job = { step: 'saving', draft };
		try {
			const saved = await saveJob(this.#api, draft);
			this.job = { step: 'saved', saved };
			if (this.session && saved.created) {
				this.session.jobs = [saved.job, ...this.session.jobs];
				this.#suggest();
			}
		} catch (error) {
			this.job = { step: 'error', message: await this.#failure(error) };
		}
	}

	/** Your details, to copy into fields the extension cannot fill. */
	async loadDetails(): Promise<string | null> {
		try {
			this.details = await this.#application();
			return null;
		} catch (error) {
			return await this.#failure(error);
		}
	}

	/** Ask to read this site from now on. Runs straight from the click (see allowSite). */
	allowThisSite(): Promise<void> {
		const pattern = this.tab?.url ? sitePattern(this.tab.url) : null;
		if (!pattern) return Promise.resolve();
		return allowSite(pattern).then((granted) => {
			this.siteAllowed = granted;
		});
	}

	async setOffer(offer: boolean): Promise<void> {
		this.settings.offer = offer;
		await saveSettings({ offer });
	}

	openApp(path: string): void {
		void chrome.tabs.create({ url: `${APP_URL}${path}` });
	}

	connect(): void {
		this.openApp(CONNECT_PATH);
	}

	async disconnect(): Promise<void> {
		if (this.#api) await disconnect(this.#api).catch(() => {});
		await forgetConnection();
	}

	/** A message for a failed call; a revoked token disconnects the panel instead. */
	async #failure(error: unknown): Promise<string> {
		if (isRevoked(error)) await forgetConnection();
		return errorMessage(error);
	}
}
