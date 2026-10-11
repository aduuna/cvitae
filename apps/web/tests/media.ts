let width = 1280;
let colorScheme: 'light' | 'dark' = 'light';
const lists = new Set<StubMediaQueryList>();

function evaluate(query: string): boolean {
	const min = /min-width:\s*(\d+)px/.exec(query);
	const max = /max-width:\s*(\d+)px/.exec(query);
	const scheme = /prefers-color-scheme:\s*(light|dark)/.exec(query);
	return (
		(!min || width >= Number(min[1])) &&
		(!max || width <= Number(max[1])) &&
		(!scheme || scheme[1] === colorScheme)
	);
}

/** Minimal MediaQueryList for width and color scheme queries, driven by the setters below. */
class StubMediaQueryList extends EventTarget {
	onchange = null;

	constructor(readonly media: string) {
		super();
	}

	get matches(): boolean {
		return evaluate(this.media);
	}

	addListener(listener: EventListener): void {
		this.addEventListener('change', listener);
	}

	removeListener(listener: EventListener): void {
		this.removeEventListener('change', listener);
	}
}

export function matchMediaStub(query: string): MediaQueryList {
	const list = new StubMediaQueryList(query);
	lists.add(list);
	return list as unknown as MediaQueryList;
}

export function setViewportWidth(px: number): void {
	width = px;
	for (const list of lists) list.dispatchEvent(new Event('change'));
}

export function setColorScheme(scheme: 'light' | 'dark'): void {
	colorScheme = scheme;
	for (const list of lists) list.dispatchEvent(new Event('change'));
}
