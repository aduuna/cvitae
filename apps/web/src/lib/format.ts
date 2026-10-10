const UNITS = ['B', 'KB', 'MB', 'GB'] as const;

/** Human-readable file size with digits and a unit, for example "340 KB" or "1.5 MB". */
export function formatBytes(bytes: number): string {
	let value = Math.max(0, bytes);
	let unit = 0;
	while (value >= 1024 && unit < UNITS.length - 1) {
		value /= 1024;
		unit += 1;
	}
	const fractionDigits = unit === 0 || value >= 10 ? 0 : 1;
	const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: fractionDigits }).format(
		value
	);
	return `${number} ${UNITS[unit]}`;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** For "Edited ...": "just now", "5 min ago", "3 h ago", "yesterday", "3 Oct" or "3 Oct 2025". */
export function formatRelative(iso: string, now: Date = new Date()): string {
	const date = new Date(iso);
	const elapsed = now.getTime() - date.getTime();
	if (elapsed < MINUTE) return 'just now';
	if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)} min ago`;
	if (elapsed < DAY && date.getDate() === now.getDate())
		return `${Math.floor(elapsed / HOUR)} h ago`;
	const yesterday = new Date(now);
	yesterday.setDate(now.getDate() - 1);
	if (date.toDateString() === yesterday.toDateString()) return 'yesterday';
	const sameYear = date.getFullYear() === now.getFullYear();
	return new Intl.DateTimeFormat('en-GB', {
		day: 'numeric',
		month: 'short',
		...(sameYear ? {} : { year: 'numeric' })
	}).format(date);
}

/** "10 Oct, 14:05" for version history. */
export function formatDateTime(iso: string): string {
	return new Intl.DateTimeFormat('en-GB', {
		day: 'numeric',
		month: 'short',
		hour: '2-digit',
		minute: '2-digit'
	}).format(new Date(iso));
}

/** "1 page", "2 pages". */
export function formatPages(count: number): string {
	return `${count} ${count === 1 ? 'page' : 'pages'}`;
}
