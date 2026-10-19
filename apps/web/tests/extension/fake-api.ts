import { vi } from 'vitest';

type Handler = (request: Request) => Response | Promise<Response>;

export function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

/** Stub fetch with one handler per "METHOD /path"; anything else is a 404 the test will notice. */
export function fakeApi(routes: Record<string, Handler>) {
	const calls: string[] = [];
	const fetch = vi.fn(async (input: RequestInfo | URL) => {
		const request = input instanceof Request ? input : new Request(input);
		const key = `${request.method} ${new URL(request.url).pathname}`;
		calls.push(key);
		const handler = routes[key];
		return handler ? handler(request) : json({ error: { code: 'not_found', message: key } }, 404);
	});
	vi.stubGlobal('fetch', fetch);
	return { calls, fetch };
}
