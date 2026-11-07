<script lang="ts">
	import { deleteAccount, exportAccount } from '#lib/account.ts';
	import { ApiError, errorMessage } from '#lib/api/client.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import { CONTACT_EMAIL } from '#lib/site.ts';

	interface Props {
		/** The account's email address: what the user types to confirm deleting it. */
		email: string;
		/** Called once the account is deleted, to end the session. */
		ondeleted: () => void | Promise<void>;
	}

	let { email, ondeleted }: Props = $props();

	let exporting = $state(false);
	let confirmOpen = $state(false);

	async function exportData() {
		exporting = true;
		try {
			await exportAccount();
			toast.info('Your data was exported.');
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			exporting = false;
		}
	}

	/** The api's reason, and for a subscription Paystack has not confirmed yet, where to turn. */
	function whyNotDeleted(error: unknown): string {
		const message = errorMessage(error);
		return error instanceof ApiError && error.details.reason === 'subscription_pending'
			? `${message} If it still does not work, write to ${CONTACT_EMAIL}.`
			: message;
	}

	/** `typed` is what the user typed to confirm; the api checks it against the account's email. */
	async function remove(typed: string) {
		try {
			await deleteAccount(typed);
		} catch (error) {
			toast.error(whyNotDeleted(error));
			return;
		}
		toast.info('Your account and everything in it was deleted.');
		await ondeleted();
	}
</script>

<Card title="Data">
	<div class="flex flex-col gap-5">
		<div class="flex flex-col items-start gap-2">
			<Button icon="download" loading={exporting} onclick={exportData}>Export data</Button>
			<p class="text-sm text-fg-muted">
				Download your profiles, CVs and their versions, saved jobs, custom templates and AI usage as
				one JSON file. Uploaded files are listed in it, not included.
			</p>
		</div>
		<div class="flex flex-col items-start gap-2 border-t border-line pt-5">
			<Button variant="danger" icon="delete" onclick={() => (confirmOpen = true)}>
				Delete account
			</Button>
			<p class="text-sm text-fg-muted">
				Permanently delete your account with all of your profiles, CVs, saved jobs, custom templates
				and uploaded files. This cannot be undone, so export your data first if you want a copy. On
				Pro, cancel your subscription first with Manage subscription under Billing.
			</p>
		</div>
	</div>
</Card>

<ConfirmDialog
	bind:open={confirmOpen}
	title="Delete account"
	message="This permanently deletes your account and everything in it: profiles, CVs, saved jobs, custom templates and uploaded files. It cannot be undone."
	confirmLabel="Delete account"
	danger
	confirmText={email}
	ignoreCase
	onconfirm={remove}
/>
