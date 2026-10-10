import { describe, expect, it } from 'vitest';
import { formatBytes } from '#lib/format.ts';

describe('formatBytes', () => {
	it.each([
		[0, '0 B'],
		[512, '512 B'],
		[1000, '1,000 B'],
		[1536, '1.5 KB'],
		[345_678, '338 KB'],
		[1024 * 1024, '1 MB'],
		[1.25 * 1024 * 1024, '1.3 MB'],
		[10 * 1024 * 1024, '10 MB'],
		[3 * 1024 ** 3, '3 GB']
	])('formats %d bytes as %s', (bytes, expected) => {
		expect(formatBytes(bytes)).toBe(expected);
	});
});
