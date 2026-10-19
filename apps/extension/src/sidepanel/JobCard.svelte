<script lang="ts">
	import Button from '@web/components/ui/Button.svelte';
	import Card from '@web/components/ui/Card.svelte';
	import Input from '@web/components/ui/Input.svelte';
	import { formatRelative } from '@web/format.ts';
	import type { JobDraft } from '../content/types.ts';
	import type { Panel } from './panel.svelte.ts';

	let { panel }: { panel: Panel } = $props();

	const job = $derived(panel.job);
	let title = $state('');
	let company = $state('');

	const FROM: Record<JobDraft['from'], string> = {
		posting: "from the page's job posting data",
		selection: 'from the text you selected',
		page: 'from the page'
	};

	$effect(() => {
		if (job.step === 'draft') {
			title = job.draft.title;
			company = job.draft.company;
		}
	});

	function tailor(jobId: string) {
		panel.openApp(`/app/tailor?job=${jobId}`);
	}
</script>

{#if panel.access === 'yes'}
	<Card title="Job ad">
		<div class="flex flex-col gap-3" aria-live="polite">
			{#if job.step === 'saved'}
				<p class="text-base text-fg">
					{job.saved.created ? 'Saved to Tailor.' : 'You saved this job before.'}
				</p>
				<div>
					<Button variant="primary" icon="tailor" onclick={() => tailor(job.saved.job.id)}>
						Tailor a CV
					</Button>
				</div>
			{:else if job.step === 'draft' || job.step === 'saving'}
				{@const draft = job.draft}
				<Input label="Job title" bind:value={title} maxlength={200} />
				<Input label="Company" bind:value={company} maxlength={200} />
				<p class="text-sm text-fg-muted">
					{draft.description.length.toLocaleString('en-US')} characters of description {FROM[
						draft.from
					]}.
					{#if draft.from === 'page'}
						For a cleaner copy, select the ad's text in the page and read it again.
					{/if}
				</p>
				<div class="flex justify-end gap-2">
					<Button variant="ghost" onclick={() => (panel.job = { step: 'idle' })}>Cancel</Button>
					<Button
						variant="primary"
						loading={job.step === 'saving'}
						onclick={() =>
							panel.saveJob({ ...draft, title: title.trim(), company: company.trim() })}
					>
						Save job
					</Button>
				</div>
			{:else if panel.pageJob}
				{@const saved = panel.pageJob}
				<p class="text-sm text-fg-muted">
					You saved this job {formatRelative(saved.created_at)}.
				</p>
				<div>
					<Button icon="tailor" onclick={() => tailor(saved.id)}>Tailor a CV</Button>
				</div>
			{:else}
				<p class="text-sm text-fg-muted">
					Save the ad on this page to Tailor, then make a CV for it.
				</p>
				{#if job.step === 'error'}
					<p class="text-sm text-danger" role="alert">{job.message}</p>
				{/if}
				<div>
					<Button loading={job.step === 'reading'} onclick={() => panel.readJob()}>
						Save job ad
					</Button>
				</div>
			{/if}
		</div>
	</Card>
{/if}
