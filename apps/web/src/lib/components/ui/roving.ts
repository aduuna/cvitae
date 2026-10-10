/**
 * Index to move to for arrow-key navigation in a one-dimensional group (radio group, tab list,
 * menu). Wraps around at both ends. Returns null for keys the group does not handle.
 */
export function nextIndex(key: string, current: number, count: number): number | null {
	if (count === 0) return null;
	switch (key) {
		case 'ArrowRight':
		case 'ArrowDown':
			return (current + 1) % count;
		case 'ArrowLeft':
		case 'ArrowUp':
			return (current - 1 + count) % count;
		case 'Home':
			return 0;
		case 'End':
			return count - 1;
		default:
			return null;
	}
}
