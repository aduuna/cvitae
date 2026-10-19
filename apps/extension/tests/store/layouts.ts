import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * The store images, as HTML pages to screenshot at their exact sizes. They use the web app's
 * colours and font, so the listing looks like the product.
 */

const web = join(import.meta.dirname, '../../../web');
const asData = (path: string, type: string) =>
	`data:${type};base64,${readFileSync(path).toString('base64')}`;

const font = asData(
	join(web, 'node_modules/@fontsource-variable/geist/files/geist-latin-wght-normal.woff2'),
	'font/woff2'
);
const logo = asData(join(web, 'static/logo.svg'), 'image/svg+xml');
const drawing = asData(join(web, 'static/illustrations/extension.svg'), 'image/svg+xml');

// The app's tokens (apps/web/src/app.css): canvas, surface, line, fg, fg-muted.
const STYLE = `
@font-face { font-family: Geist; src: url(${font}) format('woff2'); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0; }
body { font-family: Geist, sans-serif; color: #18181b; background: #f4f4f5; overflow: hidden; }
.muted { color: #71717a; }
.brand { display: flex; align-items: center; gap: 12px; font-weight: 600; }
`;

export const SCREEN = { width: 1280, height: 800 };
/** The browser window in a screenshot: its page area beside the side panel. */
export const WINDOW = { page: 820, panel: 380, height: 588, full: 1200 };

export interface Screen {
	caption: string;
	detail: string;
	/** Data URL of the page area. */
	page: string;
	/** Data URL of the side panel, or none for a page alone. */
	panel?: string;
	address: string;
}

export function screenLayout({ caption, detail, page, panel, address }: Screen): string {
	return `<!doctype html><html><head><style>${STYLE}
	header { position: absolute; left: 40px; right: 40px; top: 34px; display: flex; justify-content: space-between; align-items: flex-start; }
	h1 { font-size: 30px; line-height: 38px; font-weight: 600; letter-spacing: -0.01em; }
	header p { font-size: 17px; line-height: 24px; margin-top: 6px; }
	.brand img { width: 30px; height: 30px; }
	.brand span { font-size: 16px; }
	.window { position: absolute; left: 40px; top: 148px; width: ${WINDOW.full}px; height: ${WINDOW.height + 36}px; background: #fff; border: 1px solid #e4e4e7; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 2px rgb(0 0 0 / 0.06), 0 8px 32px rgb(0 0 0 / 0.08); }
	.bar { height: 36px; display: flex; align-items: center; gap: 8px; padding: 0 14px; border-bottom: 1px solid #e4e4e7; background: #fafafa; }
	.dot { width: 10px; height: 10px; border-radius: 50%; background: #d4d4d8; }
	.address { margin-left: 12px; padding: 4px 12px; border-radius: 6px; background: #f4f4f5; font-size: 12px; color: #71717a; width: 420px; }
	.body { display: flex; height: ${WINDOW.height}px; }
	.body img { display: block; height: ${WINDOW.height}px; }
	.panel { border-left: 1px solid #d4d4d8; }
	</style></head><body>
	<header>
		<div><h1>${caption}</h1><p class="muted">${detail}</p></div>
		<div class="brand"><img src="${logo}" alt=""><span>Chameleon vitae</span></div>
	</header>
	<div class="window">
		<div class="bar"><span class="dot"></span><span class="dot"></span><span class="dot"></span><span class="address">${address}</span></div>
		<div class="body">
			<img src="${page}" style="width:${panel ? WINDOW.page : WINDOW.full}px" alt="">
			${panel ? `<img class="panel" src="${panel}" style="width:${WINDOW.panel}px" alt="">` : ''}
		</div>
	</div>
	</body></html>`;
}

const TAGLINE = 'Fill job applications from your CV';

/** 440x280: the name, what it does, and the drawing of a form filled from a CV. */
export function smallTile(): string {
	return `<!doctype html><html><head><style>${STYLE}
	body { background: #fff; width: 440px; height: 280px; padding: 0 28px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
	.text { display: flex; flex-direction: column; gap: 18px; }
	.brand img { width: 32px; height: 32px; }
	.brand span { font-size: 17px; }
	h1 { font-size: 26px; line-height: 32px; font-weight: 600; letter-spacing: -0.01em; max-width: 200px; }
	.drawing { width: 176px; }
	</style></head><body>
		<div class="text">
			<div class="brand"><img src="${logo}" alt=""><span>Chameleon vitae</span></div>
			<h1>${TAGLINE}</h1>
		</div>
		<img class="drawing" src="${drawing}" alt="">
	</body></html>`;
}

/** 1400x560: the same, with room to say how it behaves. */
export function marqueeTile(): string {
	return `<!doctype html><html><head><style>${STYLE}
	body { background: #fff; width: 1400px; height: 560px; display: flex; align-items: center; justify-content: space-between; padding: 0 96px; }
	.text { display: flex; flex-direction: column; gap: 28px; max-width: 640px; }
	.brand img { width: 52px; height: 52px; }
	.brand span { font-size: 26px; }
	h1 { font-size: 54px; line-height: 62px; font-weight: 600; letter-spacing: -0.02em; }
	p { font-size: 22px; line-height: 32px; }
	.drawing { width: 520px; }
	</style></head><body>
		<div class="text">
			<div class="brand"><img src="${logo}" alt=""><span>Chameleon vitae</span></div>
			<h1>${TAGLINE}</h1>
			<p class="muted">Check what goes where, attach the CV you tailored, and send it yourself.</p>
		</div>
		<img class="drawing" src="${drawing}" alt="">
	</body></html>`;
}
