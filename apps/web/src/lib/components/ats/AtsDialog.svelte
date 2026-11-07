<script lang="ts">
	import { resolve } from '$app/paths';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { jobLabel } from '#lib/ats.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import Dialog from '#lib/components/ui/Dialog.svelte';
	import LinkButton from '#lib/components/ui/LinkButton.svelte';
	import Select from '#lib/components/ui/Select.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import type { DocumentAts, JobSummary } from '#lib/cv/types.ts';
	import AtsReport from './AtsReport.svelte';

	interface Props {
		open: boolean;
		documentId: string;
		/** The CV's score as last fetched; null until it is. */
		ats: DocumentAts | null;
		/** Fetch the score again, after the job or its analysis changed. */
		onchange: () => Promise<void>;
	}

	let { open = $bindable(), documentId, ats, onchange }: Props = $props();

	// The CV is checked against one saved job: choose it, have it read once (one AI run), then
	// the report. Linking a job also names the PDF for its company (docs/PRODUCT.md, 9).
	let jobs = $state<JobSummary[] | null>(null);
	let changing = $state(false);
	let jobId = $state('');
	let busy = $state<'link' | 'analyze' | null>(null);
	let error = $state<string | null>(null);

	const job = $derived(ats?.job ?? null);
	const picking = $derived(changing || job === null);

	$effect(() => {
		if (open && picking && jobs === null) void loadJobs();
	});

	function reset() {
		changing = false;
		error = null;
	}

	function dismiss() {
		open = false;
		reset();
	}

	function changeJob() {
		changing = true;
		if (job && jobs?.some((row) => row.id === job.id)) jobId = job.id;
	}

	async function loadJobs() {
		try {
			jobs = await unwrap(api.GET('/api/v1/jobs'));
			jobId = jobs.some((row) => row.id === job?.id) ? (job?.id ?? '') : (jobs[0]?.id ?? '');
		} catch (err) {
			error = errorMessage(err);
		}
	}

	async function link() {
		busy = 'link';
		error = null;
		try {
			await unwrap(
				api.PATCH('/api/v1/documents/{document_id}', {
					params: { path: { document_id: documentId } },
					body: { job_id: jobId }
				})
			);
			changing = false;
			await onchange();
		} catch (err) {
			error = errorMessage(err);
		} finally {
			busy = null;
		}
	}

	async function analyze() {
		if (!job) return;
		busy = 'analyze';
		error = null;
		try {
			await unwrap(
				api.POST('/api/v1/jobs/{job_id}/analyze', {
					params: { path: { job_id: job.id } },
					body: {}
				})
			);
			session.refreshUsage().catch(() => {});
			await onchange();
		} catch (err) {
			error = errorMessage(err);
		} finally {
			busy = null;
		}
	}
</script>

<Dialog bind:open title="ATS score" size="md" onclose={reset}>
	<div class="flex flex-col gap-4">
		{#if picking}
			{#if jobs === null && !error}
				<Skeleton lines={2} />
			{:else if jobs !== null && jobs.length === 0}
				<p class="text-base text-fg">
					No saved jobs yet. A job is saved when you tailor a CV for it, or save its ad with the
					browser extension.
				</p>
			{:else if jobs !== null}
				<p class="text-sm text-fg-muted">
					Choose the job to check this CV against. The exported PDF is then named for its company.
				</p>
				<Select
					label="Job"
					bind:value={jobId}
					options={jobs.map((row) => ({ value: row.id, label: jobLabel(row) }))}
				/>
			{/if}
		{:else if job && !ats?.report}
			<p class="text-base text-fg">
				{jobLabel(job)} has not been read yet. Reading the job ad takes a little of your AI usage, once.
			</p>
		{:else if job && ats?.report}
			<div class="flex items-center justify-between gap-4">
				<p class="min-w-0 truncate text-sm text-fg-muted">For {jobLabel(job)}</p>
				<Button variant="ghost" size="sm" onclick={changeJob}>Change job</Button>
			</div>
			<AtsReport report={ats.report} level={3} />
		{/if}
		{#if error}
			<p role="alert" class="text-sm text-danger">{error}</p>
		{/if}
	</div>

	{#snippet footer()}
		{#if picking && jobs !== null && jobs.length === 0}
			<LinkButton href={resolve('/app/tailor')}>Go to Tailor</LinkButton>
		{:else if picking}
			{#if changing}
				<Button variant="ghost" onclick={() => (changing = false)}>Cancel</Button>
			{/if}
			<Button variant="primary" disabled={!jobId} loading={busy === 'link'} onclick={link}>
				Check against this job
			</Button>
		{:else if job && !ats?.report}
			<Button variant="primary" loading={busy === 'analyze'} onclick={analyze}>
				Read the job ad
			</Button>
		{:else}
			<Button variant="secondary" onclick={dismiss}>Close</Button>
		{/if}
	{/snippet}
</Dialog>
