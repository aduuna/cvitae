<script lang="ts">
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import Dialog from '#lib/components/ui/Dialog.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import type { CvDocument, Version } from '#lib/cv/types.ts';
	import { formatDateTime } from '#lib/format.ts';

	interface Props {
		open: boolean;
		documentId: string;
		/** Saves pending edits first, so versions hold the latest content. */
		beforeChange: () => Promise<void>;
		onrestored: (document: CvDocument) => void;
	}

	let { open = $bindable(), documentId, beforeChange, onrestored }: Props = $props();

	const reasons: Record<Version['reason'], string> = {
		manual: 'Saved by you',
		restore: 'Restored',
		autosave: 'Kept before a restore',
		tailor: 'Tailored'
	};

	let versions = $state<Version[] | null>(null);
	let saving = $state(false);
	let restoring = $state<number | null>(null);

	const path = $derived({ params: { path: { document_id: documentId } } });

	async function load() {
		try {
			versions = await unwrap(api.GET('/api/v1/documents/{document_id}/versions', path));
		} catch (error) {
			toast.error(errorMessage(error));
		}
	}

	$effect(() => {
		if (open) {
			versions = null;
			void load();
		}
	});

	async function save() {
		saving = true;
		try {
			await beforeChange();
			const version = await unwrap(api.POST('/api/v1/documents/{document_id}/versions', path));
			toast.info(`Saved version ${version.number}.`);
			await load();
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			saving = false;
		}
	}

	async function restore(number: number) {
		restoring = number;
		try {
			await beforeChange();
			const document = await unwrap(
				api.POST('/api/v1/documents/{document_id}/versions/{number}/restore', {
					params: { path: { document_id: documentId, number } }
				})
			);
			onrestored(document);
			toast.info(`Restored version ${number}. Your previous content is kept as a version.`);
			open = false;
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			restoring = null;
		}
	}
</script>

<Dialog bind:open title="Version history" size="md">
	<p class="text-sm text-fg-muted">
		Save a version before big changes. Restoring keeps your current content as a version too.
	</p>
	<div class="mt-4">
		{#if versions === null}
			<Skeleton lines={3} />
		{:else if versions.length === 0}
			<p class="text-base text-fg-muted">No versions yet.</p>
		{:else}
			<ul aria-label="Versions" class="flex max-h-80 flex-col overflow-y-auto">
				{#each versions as version (version.number)}
					<li class="flex h-12 items-center gap-3 border-b border-line last:border-b-0">
						<span class="w-24 text-base font-medium text-fg">Version {version.number}</span>
						<span class="min-w-0 flex-1 truncate text-sm text-fg-muted">
							{reasons[version.reason]}, {formatDateTime(version.created_at)}
						</span>
						<Button
							size="sm"
							loading={restoring === version.number}
							disabled={restoring !== null}
							onclick={() => restore(version.number)}
							aria-label="Restore version {version.number}"
						>
							Restore
						</Button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
	{#snippet footer()}
		<Button onclick={() => (open = false)}>Close</Button>
		<Button variant="primary" icon="versions" loading={saving} onclick={save}>Save version</Button>
	{/snippet}
</Dialog>
