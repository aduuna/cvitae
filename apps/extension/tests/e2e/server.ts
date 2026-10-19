import { readFileSync } from 'node:fs';
import { createServer, type IncomingMessage, type Server } from 'node:http';
import { join } from 'node:path';

export const E2E_PORT = 4799;
export const E2E_APP_URL = `http://localhost:${E2E_PORT}`;
export const E2E_OUT_DIR = 'dist-e2e';
export const TOKEN = 'cvx_e2e';
export const JOB_URL = 'https://job-boards.greenhouse.io/harbour/jobs/4012345';

const fixtures = join(import.meta.dirname, '..', 'fixtures');
const at = '2026-10-01T09:00:00Z';

const session = {
	email: 'ama@example.com',
	display_name: 'Ama',
	profiles: [{ id: 'p1', name: 'Data engineering', is_default: true, updated_at: at }],
	documents: [{ id: 'd1', name: 'Harbour Bank CV', job_id: 'j1', placeholders: 0, updated_at: at }],
	jobs: [
		{
			id: 'j1',
			title: 'Data engineer',
			company: 'Harbour Bank',
			url: JOB_URL,
			created_at: at,
			updated_at: at
		}
	]
};

/**
 * Stands in for the web app's connect page: it pings the extension, hands over a token when the
 * extension answers, and shows the outcome.
 */
const CONNECT_PAGE = `<!doctype html>
<title>Connect the extension</title>
<p id="status">Waiting for the extension</p>
<script>
	let sent = false;
	addEventListener('message', (event) => {
		if (event.source !== window || event.origin !== location.origin) return;
		const message = event.data;
		if (!message || message.source !== 'cvitae-extension') return;
		if (message.type === 'ready' && !sent) {
			sent = true;
			postMessage({ source: 'cvitae-app', type: 'token', token: '${TOKEN}', email: 'ama@example.com' }, location.origin);
		}
		// Not the global "status": that is window.status, a string.
		const shown = document.getElementById('status');
		if (message.type === 'connected') shown.textContent = 'Connected to ' + message.email;
		if (message.type === 'failed') shown.textContent = 'Failed: ' + message.message;
	});
	postMessage({ source: 'cvitae-app', type: 'ping' }, location.origin);
</script>`;

/** A Greenhouse job page: the ad's posting data, the new board's form and a CV upload. */
export function jobPage(): string {
	const posting = {
		'@context': 'https://schema.org',
		'@type': 'JobPosting',
		title: 'Data Engineer',
		hiringOrganization: { '@type': 'Organization', name: 'Harbour Bank' },
		description: '<p>Build streaming pipelines.</p>'
	};
	// Fields a page could hide to collect more than it shows: off the page, transparent, tiny.
	const concealed = `
		<label for="trap-email">Email</label><input id="trap-email" style="position:absolute;left:-9999px">
		<label for="trap-phone">Phone</label><input id="trap-phone" style="opacity:0">
		<label for="trap-name">Full name</label><input id="trap-name" style="width:1px;height:1px;padding:0;border:0">`;
	const form = readFileSync(join(fixtures, 'greenhouse-new.html'), 'utf8').replace(
		'</form>',
		`<label for="resume">Resume/CV</label><input id="resume" type="file" accept=".pdf">${concealed}</form>`
	);
	return `<!doctype html><html><head><title>Data Engineer at Harbour Bank</title>
		<script type="application/ld+json">${JSON.stringify(posting)}</script></head>
		<body><h1>Data Engineer</h1>${form}</body></html>`;
}

export interface MockApi {
	requests: string[];
	savedJobs: unknown[];
	close(): Promise<void>;
}

function body(request: IncomingMessage): Promise<string> {
	return new Promise((resolve) => {
		let data = '';
		request.on('data', (chunk) => (data += chunk));
		request.on('end', () => resolve(data));
	});
}

export function startServer(): Promise<MockApi> {
	const requests: string[] = [];
	const savedJobs: unknown[] = [];
	const application = readFileSync(join(fixtures, 'application-sample.json'), 'utf8');
	const server: Server = createServer(async (request, response) => {
		const path = new URL(request.url ?? '/', E2E_APP_URL).pathname;
		const key = `${request.method} ${path}`;
		requests.push(key);
		const send = (status: number, content: string, type = 'application/json') => {
			response.writeHead(status, { 'Content-Type': type });
			response.end(content);
		};
		if (path === '/app/extension') return send(200, CONNECT_PAGE, 'text/html');
		if (request.headers.authorization !== `Bearer ${TOKEN}`) {
			return send(401, JSON.stringify({ error: { code: 'unauthorized', message: 'No.' } }));
		}
		switch (key) {
			case 'GET /api/v1/extension/session':
				return send(200, JSON.stringify(session));
			case 'GET /api/v1/extension/profiles/p1/application':
			case 'GET /api/v1/extension/documents/d1/application':
				return send(200, application);
			case 'GET /api/v1/extension/documents/d1/cv.pdf':
				response.writeHead(200, {
					'Content-Type': 'application/pdf',
					'Content-Disposition': 'attachment; filename="Ama-Owusu-Mensah-CV-Harbour-Bank.pdf"'
				});
				return response.end('%PDF-1.7\n% e2e\n');
			case 'POST /api/v1/extension/jobs': {
				const job = JSON.parse(await body(request)) as Record<string, unknown>;
				savedJobs.push(job);
				return send(
					201,
					JSON.stringify({
						job: { id: 'j2', ...job, created_at: at, updated_at: at },
						created: true
					})
				);
			}
			default:
				return send(404, JSON.stringify({ error: { code: 'not_found', message: key } }));
		}
	});
	return new Promise((resolve) =>
		server.listen(E2E_PORT, () =>
			resolve({
				requests,
				savedJobs,
				close: () => new Promise((done) => server.close(() => done()))
			})
		)
	);
}
