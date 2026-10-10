import { describe, expect, it } from 'vitest';
import { formatBytes, formatDateTime, formatPages, formatRelative } from '#lib/format.ts';

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

describe('formatRelative', () => {
	const now = new Date('2026-10-10T15:00:00');
	it.each([
		['2026-10-10T14:59:30', 'just now'],
		['2026-10-10T14:55:00', '5 min ago'],
		['2026-10-10T12:00:00', '3 h ago'],
		['2026-10-09T22:00:00', 'yesterday'],
		['2026-10-03T10:00:00', '3 Oct'],
		['2025-10-03T10:00:00', '3 Oct 2025']
	])('formats %s as %s', (iso, expected) => {
		expect(formatRelative(iso, now)).toBe(expected);
	});
});

describe('formatPages', () => {
	it('uses the singular for one page', () => {
		expect(formatPages(1)).toBe('1 page');
		expect(formatPages(2)).toBe('2 pages');
	});
});

describe('formatDateTime', () => {
	it('shows day, month and time', () => {
		expect(formatDateTime('2026-10-10T14:05:00')).toBe('10 Oct, 14:05');
	});
});
