import { describe, expect, it } from 'vitest';
import {
	areaAt,
	mergeLines,
	sourceAreas,
	sourceField,
	type SourceArea
} from '#lib/source-links.ts';

// The shape Typst writes: groups with translate or matrix transforms, and one transparent rect per
// line of linked text inside an <a> with its own translate. Real entries link only their own lines,
// but entry-1 here also covers bullet-1, to show the smaller area winning.
const SVG = `<svg viewBox="0 0 200 100" width="200pt" height="100pt" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
	<g transform="translate(10 20)">
		<a transform="translate(5 5)" href="cv:entry-1" xlink:href="cv:entry-1"><rect width="100" height="30" fill="transparent"/></a>
		<g transform="matrix(1 0 0 1 20 10)">
			<a transform="translate(0 0)" xlink:href="cv:bullet-1"><rect width="40" height="10" fill="transparent"/></a>
		</g>
	</g>
	<a transform="translate(20 60)" href="cv:bullet-2"><rect width="60" height="8"/></a>
	<a transform="translate(20 68.4)" href="cv:bullet-2"><rect width="40" height="8"/></a>
	<a transform="translate(0 90)" href="https://example.com"><rect width="50" height="10"/></a>
	<a transform="translate(150 0) scale(2)" href="cv:basics"><rect x="1" y="1" width="10" height="5"/></a>
</svg>`;

function rounded(area: SourceArea): SourceArea {
	const round = (n: number) => Math.round(n * 1000) / 1000;
	return {
		target: area.target,
		x: round(area.x),
		y: round(area.y),
		width: round(area.width),
		height: round(area.height)
	};
}

describe('sourceAreas', () => {
	it('reads each cv link as a fraction of the page, through every transform', () => {
		expect(sourceAreas(SVG).map(rounded)).toEqual([
			{ target: 'entry-1', x: 0.075, y: 0.25, width: 0.5, height: 0.3 },
			{ target: 'bullet-1', x: 0.15, y: 0.3, width: 0.2, height: 0.1 },
			{ target: 'bullet-2', x: 0.1, y: 0.6, width: 0.3, height: 0.08 },
			{ target: 'bullet-2', x: 0.1, y: 0.684, width: 0.2, height: 0.08 },
			{ target: 'basics', x: 0.76, y: 0.02, width: 0.1, height: 0.1 }
		]);
	});

	it('finds nothing in a page without a view box', () => {
		expect(sourceAreas('<svg xmlns="http://www.w3.org/2000/svg"/>')).toEqual([]);
	});
});

describe('areaAt', () => {
	const areas = sourceAreas(SVG);

	it('prefers the smallest area under the point, so a bullet wins over its entry', () => {
		expect(areaAt(areas, 0.2, 0.35)?.target).toBe('bullet-1');
		expect(areaAt(areas, 0.1, 0.5)?.target).toBe('entry-1');
	});

	it('counts a point just outside an area, such as the gap between lines, as that area', () => {
		// Between the two lines of bullet-2 (y 0.680 to 0.684).
		expect(areaAt(areas, 0.15, 0.682)?.target).toBe('bullet-2');
		expect(areaAt(areas, 0.95, 0.95)).toBeNull();
	});
});

describe('mergeLines', () => {
	it('joins the runs of one line into one box and keeps separate lines apart', () => {
		const run = (x: number, y: number, width: number, height = 0.02) => ({
			target: 'b1',
			x,
			y,
			width,
			height
		});

		expect(
			mergeLines([run(0.1, 0.5, 0.2), run(0.3, 0.501, 0.1, 0.018), run(0.1, 0.53, 0.3)]).map(
				rounded
			)
		).toEqual([run(0.1, 0.5, 0.3), run(0.1, 0.53, 0.3)]);
	});
});

describe('sourceField', () => {
	it('finds a bullet, the summary, or the first field of an item, section or the header', () => {
		document.body.innerHTML = `
			<div data-cv-id="basics"><button>Menu</button><input aria-label="Name" /></div>
			<textarea data-field="summary"></textarea>
			<section data-cv-id="s1"><input aria-label="Section title" />
				<div data-cv-id="e1"><input aria-label="Organisation" /><textarea data-bullet-id="b1"></textarea></div>
			</section>`;
		const label = (target: string) => sourceField(document, target)?.getAttribute('aria-label');

		expect(sourceField(document, 'b1')).toBe(document.querySelector('[data-bullet-id="b1"]'));
		expect(sourceField(document, 'summary')).toBe(document.querySelector('[data-field="summary"]'));
		expect([label('basics'), label('s1'), label('e1')]).toEqual([
			'Name',
			'Section title',
			'Organisation'
		]);
		expect(sourceField(document, 'gone')).toBeNull();
	});
});
