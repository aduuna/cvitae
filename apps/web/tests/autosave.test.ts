import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '#lib/api/client.ts';
import { Autosave } from '#lib/autosave.svelte.ts';

function deferred() {
	let resolve!: () => void;
	let reject!: (error: unknown) => void;
	const promise = new Promise<void>((res, rej) => {
		resolve = res;
		reject = rej;
	});
	return { promise, resolve, reject };
}

describe('Autosave', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('debounces edits into one save of the latest value', async () => {
		const save = vi.fn(async () => {});
		const autosave = new Autosave(save, { v: 0 }, 400);

		autosave.schedule({ v: 1 });
		autosave.schedule({ v: 2 });
		expect(autosave.status).toBe('unsaved');
		await vi.advanceTimersByTimeAsync(399);
		expect(save).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(1);

		expect(save).toHaveBeenCalledExactlyOnceWith({ v: 2 });
		expect(autosave.status).toBe('saved');
		expect(autosave.dirty).toBe(false);
	});

	it('skips values equal to the last saved one', async () => {
		const save = vi.fn(async () => {});
		const autosave = new Autosave(save, { v: 0 }, 400);

		autosave.schedule({ v: 0 });
		await vi.advanceTimersByTimeAsync(500);

		expect(save).not.toHaveBeenCalled();
		expect(autosave.status).toBe('saved');
	});

	it('saves edits made during a save afterwards, one save at a time', async () => {
		const first = deferred();
		const save = vi.fn().mockReturnValueOnce(first.promise).mockResolvedValue(undefined);
		const autosave = new Autosave(save, { v: 0 }, 100);

		autosave.schedule({ v: 1 });
		await vi.advanceTimersByTimeAsync(100);
		expect(autosave.status).toBe('saving');
		autosave.schedule({ v: 2 });
		await vi.advanceTimersByTimeAsync(100);
		expect(save).toHaveBeenCalledTimes(1);
		first.resolve();
		await vi.advanceTimersByTimeAsync(0);

		expect(save).toHaveBeenNthCalledWith(2, { v: 2 });
		expect(autosave.status).toBe('saved');
	});

	it('settles on saved when an edit is undone during a save', async () => {
		const first = deferred();
		const save = vi.fn().mockReturnValueOnce(first.promise);
		const autosave = new Autosave(save, { v: 0 }, 100);

		autosave.schedule({ v: 1 });
		await vi.advanceTimersByTimeAsync(100);
		autosave.schedule({ v: 1 });
		first.resolve();
		await vi.advanceTimersByTimeAsync(200);

		expect(save).toHaveBeenCalledTimes(1);
		expect(autosave.status).toBe('saved');
	});

	it('keeps a failed value and retries it on flush', async () => {
		const save = vi
			.fn()
			.mockRejectedValueOnce(new ApiError(422, 'validation_failed', 'Check the link.'))
			.mockResolvedValue(undefined);
		const autosave = new Autosave(save, { v: 0 }, 100);

		autosave.schedule({ v: 1 });
		await vi.advanceTimersByTimeAsync(100);
		expect(autosave.status).toBe('error');
		expect(autosave.error).toBe('Check the link.');
		expect(autosave.dirty).toBe(true);

		await autosave.flush();
		expect(save).toHaveBeenLastCalledWith({ v: 1 });
		expect(autosave.status).toBe('saved');
		expect(autosave.error).toBeNull();
	});

	it('flush saves at once and reset adopts a server value', async () => {
		const save = vi.fn(async () => {});
		const autosave = new Autosave(save, { v: 0 }, 1000);

		autosave.schedule({ v: 1 });
		await autosave.flush();
		expect(save).toHaveBeenCalledOnce();

		autosave.reset({ v: 5 });
		autosave.schedule({ v: 5 });
		await vi.advanceTimersByTimeAsync(2000);
		expect(save).toHaveBeenCalledOnce();
		expect(autosave.status).toBe('saved');
		autosave.dispose();
	});
});
