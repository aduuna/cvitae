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
