export type ToastKind = 'info' | 'error';

export interface ToastItem {
	id: number;
	kind: ToastKind;
	message: string;
}

/** Info toasts close after this long; error toasts stay until dismissed. */
export const INFO_TOAST_MS = 4000;

class Toasts {
	items = $state<ToastItem[]>([]);
	#nextId = 1;

	info(message: string): number {
		const id = this.#push('info', message);
		setTimeout(() => this.dismiss(id), INFO_TOAST_MS);
		return id;
	}

	error(message: string): number {
		return this.#push('error', message);
	}

	dismiss(id: number): void {
		this.items = this.items.filter((item) => item.id !== id);
	}

	clear(): void {
		this.items = [];
	}

	#push(kind: ToastKind, message: string): number {
		const id = this.#nextId++;
		this.items = [...this.items, { id, kind, message }];
		return id;
	}
}

/** App-wide toast queue. Render <Toast /> once in the app shell. */
export const toast = new Toasts();
