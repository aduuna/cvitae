import { errorMessage } from '#lib/api/client.ts';

export type SaveStatus = 'saved' | 'unsaved' | 'saving' | 'error';

/** What a save indicator needs from an Autosave, whatever it saves. */
export interface SaveState {
	readonly status: SaveStatus;
	readonly error: string | null;
	flush(): Promise<void>;
}

/** Status text for the top bar. */
export const saveStatusText: Record<SaveStatus, string> = {
	saved: 'Saved',
	unsaved: 'Unsaved changes',
	saving: 'Saving',
	error: 'Not saved'
};

/**
 * Debounced saving with a visible status. `schedule` takes the latest value; saves run one at a
 * time, and values equal to the last saved one are skipped. A failed save keeps the value so the
 * next edit (or `flush`) retries it.
 */
export class Autosave<T> implements SaveState {
	status = $state<SaveStatus>('saved');
	error = $state<string | null>(null);

	#save: (value: T) => Promise<void>;
	#delay: number;
	#timer: ReturnType<typeof setTimeout> | undefined;
	#pending: { value: T; key: string } | null = null;
	#inflight: Promise<void> | null = null;
	#lastSaved: string;

	constructor(save: (value: T) => Promise<void>, initial: T, delay = 600) {
		this.#save = save;
		this.#delay = delay;
		this.#lastSaved = JSON.stringify(initial);
	}

	/** Changes with unsaved or in-flight values. */
	get dirty(): boolean {
		return this.#pending !== null || this.#inflight !== null;
	}

	/** Queue the latest value. Call it from an effect inside `untrack`, so the effect does not
	 * depend on `status`. */
	schedule(value: T): void {
		const key = JSON.stringify(value);
		clearTimeout(this.#timer);
		if (key === this.#lastSaved && !this.#inflight) {
			this.#pending = null;
			if (this.status !== 'error') this.status = 'saved';
			return;
		}
		this.#pending = { value, key };
		if (this.status !== 'error') this.status = 'unsaved';
		this.#timer = setTimeout(() => void this.flush(), this.#delay);
	}

	/** Treat `value` as saved, for example after loading or restoring from the server. */
	reset(value: T): void {
		clearTimeout(this.#timer);
		this.#pending = null;
		this.#lastSaved = JSON.stringify(value);
		this.status = 'saved';
		this.error = null;
	}

	/** Save now. Resolves once everything scheduled so far is saved or has failed. */
	async flush(): Promise<void> {
		clearTimeout(this.#timer);
		while (this.#inflight) await this.#inflight;
		const pending = this.#pending;
		if (!pending || pending.key === this.#lastSaved) {
			this.#pending = null;
			if (this.status !== 'error') this.status = 'saved';
			return;
		}
		this.#pending = null;
		this.status = 'saving';
		this.#inflight = this.#save(pending.value).then(
			() => {
				this.#lastSaved = pending.key;
				this.error = null;
				this.status = this.#pending ? 'unsaved' : 'saved';
			},
			(error: unknown) => {
				this.#pending ??= pending;
				this.error = errorMessage(error);
				this.status = 'error';
			}
		);
		try {
			await this.#inflight;
		} finally {
			this.#inflight = null;
		}
	}

	dispose(): void {
		clearTimeout(this.#timer);
	}
}
