import { api, filenameFrom, saveFile, unwrap } from '#lib/api/client.ts';

const EXPORT_FILENAME = 'chameleon-vitae-export.json';

/** Download everything the account holds as one JSON file. Throws an ApiError on failure. */
export async function exportAccount(): Promise<void> {
	let response: Response | undefined;
	const data = await unwrap(
		api.GET('/api/v1/me/export', { parseAs: 'blob' }).then((result) => {
			response = result.response;
			return result;
		})
	);
	saveFile(
		data as Blob,
		filenameFrom(response?.headers.get('content-disposition') ?? null, EXPORT_FILENAME)
	);
}

/**
 * Delete the account, its data and its stored files. `email` is the address the user typed to
 * confirm; the api compares it with the account's. Throws an ApiError on failure.
 */
export async function deleteAccount(email: string): Promise<void> {
	await unwrap(api.DELETE('/api/v1/me', { body: { email } }));
}
