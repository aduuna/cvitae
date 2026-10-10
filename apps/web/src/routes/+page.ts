import { redirect } from '@sveltejs/kit';

// No landing page until sign-in exists (M2); go straight to the app.
export function load() {
	redirect(307, '/app/documents');
}
