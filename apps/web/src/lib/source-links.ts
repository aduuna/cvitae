/**
 * Click-to-edit for previews. The renderer links each part of a previewed CV to its form field
 * (`cv:<id>`, `cv:summary` or `cv:basics`): Typst draws a transparent rectangle per line of linked
 * text. Pages are shown as images, which cannot be clicked into, so these areas are read from the
 * SVG and hit-tested against the pointer instead.
 */

/** A linked part of a page, in fractions of the page so it holds at any zoom. */
export interface SourceArea {
	/** An item, section or bullet id, or "summary" or "basics". */
	target: string;
	x: number;
	y: number;
	width: number;
	height: number;
}

type Matrix = [number, number, number, number, number, number];

const IDENTITY: Matrix = [1, 0, 0, 1, 0, 0];
const XLINK = 'http://www.w3.org/1999/xlink';

function multiply([a, b, c, d, e, f]: Matrix, [g, h, i, j, k, l]: Matrix): Matrix {
	return [
		a * g + c * h,
		b * g + d * h,
		a * i + c * j,
		b * i + d * j,
		a * k + c * l + e,
		b * k + d * l + f
	];
}

/** An SVG transform attribute as one matrix; Typst writes translate and matrix. */
function parseTransform(value: string | null): Matrix {
	let result = IDENTITY;
	for (const [, name, args] of (value ?? '').matchAll(/(\w+)\(([^)]*)\)/g)) {
		const n = (args ?? '')
			.trim()
			.split(/[\s,]+/)
			.map(Number);
		const step: Matrix | null =
			name === 'translate'
				? [1, 0, 0, 1, n[0] ?? 0, n[1] ?? 0]
				: name === 'scale'
					? [n[0] ?? 1, 0, 0, n[1] ?? n[0] ?? 1, 0, 0]
					: name === 'matrix' && n.length === 6
						? (n as Matrix)
						: null;
		if (step) result = multiply(result, step);
	}
	return result;
}

/** The linked areas of one SVG page, in reading order. */
export function sourceAreas(svg: string): SourceArea[] {
	const root = new DOMParser().parseFromString(svg, 'image/svg+xml').documentElement;
	const [, , pageWidth = 0, pageHeight = 0] = (root.getAttribute('viewBox') ?? '')
		.trim()
		.split(/[\s,]+/)
		.map(Number);
	if (!(pageWidth > 0 && pageHeight > 0)) return [];

	const areas: SourceArea[] = [];
	for (const link of root.getElementsByTagNameNS('*', 'a')) {
		const href = link.getAttribute('href') ?? link.getAttributeNS(XLINK, 'href') ?? '';
		const rect = link.getElementsByTagNameNS('*', 'rect')[0];
		if (!href.startsWith('cv:') || !rect) continue;

		let matrix = IDENTITY;
		for (let node: Element | null = link; node && node !== root; node = node.parentElement) {
			matrix = multiply(parseTransform(node.getAttribute('transform')), matrix);
		}
		const [x, y] = [Number(rect.getAttribute('x') ?? 0), Number(rect.getAttribute('y') ?? 0)];
		const [w, h] = [Number(rect.getAttribute('width')), Number(rect.getAttribute('height'))];
		const corners = [
			[x, y],
			[x + w, y],
			[x, y + h],
			[x + w, y + h]
		].map(([px = 0, py = 0]) => [
			matrix[0] * px + matrix[2] * py + matrix[4],
			matrix[1] * px + matrix[3] * py + matrix[5]
		]);
		const xs = corners.map(([px = 0]) => px);
		const ys = corners.map(([, py = 0]) => py);
		const left = Math.min(...xs);
		const top = Math.min(...ys);
		areas.push({
			target: href.slice(3),
			x: left / pageWidth,
			y: top / pageHeight,
			width: (Math.max(...xs) - left) / pageWidth,
			height: (Math.max(...ys) - top) / pageHeight
		});
	}
	return areas;
}

/**
 * The area under a point (fractions of the page): the smallest one containing it, so a bullet
 * wins over the entry around it, else the nearest within `slack`, so the gap between two lines of
 * one bullet still counts as that bullet.
 */
export function areaAt(
	areas: SourceArea[],
	x: number,
	y: number,
	slack = 0.006
): SourceArea | null {
	let best: SourceArea | null = null;
	let bestDistance = Infinity;
	for (const area of areas) {
		const dx = Math.max(area.x - x, 0, x - (area.x + area.width));
		const dy = Math.max(area.y - y, 0, y - (area.y + area.height));
		const distance = Math.hypot(dx, dy);
		if (distance > slack) continue;
		const smaller = best !== null && area.width * area.height < best.width * best.height;
		if (distance < bestDistance || (distance === bestDistance && smaller)) {
			best = area;
			bestDistance = distance;
		}
	}
	return best;
}

/** The areas joined into one box per line: Typst draws a rect per text run, so a line that mixes
 * bold and plain text, or a name and a right-aligned date, has several. */
export function mergeLines(areas: SourceArea[]): SourceArea[] {
	const lines: SourceArea[] = [];
	for (const area of areas) {
		const line = lines.find(
			(other) =>
				Math.abs(other.y + other.height / 2 - (area.y + area.height / 2)) <
				Math.min(other.height, area.height) / 2
		);
		if (!line) {
			lines.push({ ...area });
			continue;
		}
		const right = Math.max(line.x + line.width, area.x + area.width);
		const bottom = Math.max(line.y + line.height, area.y + area.height);
		line.x = Math.min(line.x, area.x);
		line.y = Math.min(line.y, area.y);
		line.width = right - line.x;
		line.height = bottom - line.y;
	}
	return lines;
}

/** The form control holding a link target, inside `root`: the field itself, or the first field of
 * the item, section or header it names. */
export function sourceField(root: ParentNode, target: string): HTMLElement | null {
	const id = CSS.escape(target);
	const match = root.querySelector<HTMLElement>(
		`[data-bullet-id="${id}"], [data-field="${id}"], [data-cv-id="${id}"]`
	);
	if (!match || match.matches('input, textarea, select')) return match;
	return match.querySelector<HTMLElement>('input, textarea, select');
}
