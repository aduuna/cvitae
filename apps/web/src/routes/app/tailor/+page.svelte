<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { modelLabel, otherModels, pickModel } from '#lib/ai/models.ts';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import { blockedReason, canUpgrade } from '#lib/billing/plans.ts';
	import LimitNotice from '#lib/components/billing/LimitNotice.svelte';
	import GenerationProgress from '#lib/components/ai/GenerationProgress.svelte';
	import ModelSelect from '#lib/components/ai/ModelSelect.svelte';
	import Page from '#lib/components/shell/Page.svelte';
	import TailorReview from '#lib/components/tailor/TailorReview.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';
	import EmptyState from '#lib/components/ui/EmptyState.svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import Select from '#lib/components/ui/Select.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import Textarea from '#lib/components/ui/Textarea.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import Menu from '#lib/components/ui/Menu.svelte';
	import type { AiModel, JobSummary, ProfileSummary, TailorResult } from '#lib/cv/types.ts';
	import { formatRelative } from '#lib/format.ts';
	import { DEFAULT_TEMPLATE_ID, templates } from '#lib/templates.svelte.ts';

	const STEPS = [
		'Reading the job description',
		'Selecting your strongest experience',
		'Writing the CV'
	];

	let phase = $state<'form' | 'running' | 'review'>('form');
	let profiles = $state<ProfileSummary[] | null>(null);
	let jobs = $state<JobSummary[]>([]);

	let description = $state('');
	let title = $state('');
	let company = $state('');
	let url = $state('');
	let savedJob = $state<JobSummary | null>(null);
	let profileId = $state('');
	let templateId = $state(DEFAULT_TEMPLATE_ID);
	let model = $state<AiModel | null>(null);
	let error = $state<string | null>(null);
	let controller: AbortController | null = null;

	let result = $state<TailorResult | null>(null);
	let busy = $state<'discard' | 'regenerate' | null>(null);
	let deletingJob = $state<JobSummary | null>(null);
	let deleteOpen = $state(false);

	/** Tailoring makes a CV and takes AI runs: set when either limit is reached. */
	const blocked = $derived(
		blockedReason(session.usage?.ai_runs, {
			meter: session.usage?.documents,
			what: 'Tailoring makes a new CV.'
		})
	);
	const ready = $derived(
		model !== null &&
			blocked === null &&
			profileId !== '' &&
			(savedJob !== null || description.trim() !== '')
	);

	function refreshUsage() {
		session.refreshUsage().catch(() => {});
	}

	onMount(async () => {
		try {
			const [me, profileList, jobList] = await Promise.all([
				session.loadMe(),
				unwrap(api.GET('/api/v1/profiles')),
				unwrap(api.GET('/api/v1/jobs')),
				templates.load()
			]);
			profiles = profileList;
			jobs = jobList;
			profileId = (profileList.find((p) => p.is_default) ?? profileList[0])?.id ?? '';
			templateId = me.default_template_id ?? DEFAULT_TEMPLATE_ID;
			model = pickModel(me.preferred_ai_model, session.aiModels, session.defaultAiModel);
		} catch (failure) {
			error = errorMessage(failure);
			profiles = [];
		}
		refreshUsage();
	});

	async function run(chosen: AiModel, jobId: string | null) {
		phase = 'running';
		error = null;
		controller = new AbortController();
		try {
			result = await unwrap(
				api.POST('/api/v1/tailor', {
					body: {
						profile_id: profileId,
						template_id: templateId,
						ai_model: chosen,
						...(jobId
							? { job_id: jobId }
							: {
									job: {
										description: description.trim(),
										title: title.trim(),
										company: company.trim(),
										url: url.trim() || null
									}
								})
					},
					signal: controller.signal
				})
			);
			phase = 'review';
			const job = result.job;
			jobs = [job, ...jobs.filter((row) => row.id !== job.id)];
		} catch (failure) {
			phase = 'form';
			if (!(failure instanceof DOMException && failure.name === 'AbortError')) {
				error = errorMessage(failure);
			}
		} finally {
			controller = null;
			refreshUsage();
		}
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (model) void run(model, savedJob?.id ?? null);
	}

	async function deleteDraft(): Promise<boolean> {
		if (!result) return true;
		try {
			await unwrap(
				api.DELETE('/api/v1/documents/{document_id}', {
					params: { path: { document_id: result.document.id } }
				})
			);
			return true;
		} catch (failure) {
			toast.error(errorMessage(failure));
			return false;
		}
	}

	async function discard() {
		busy = 'discard';
		if (await deleteDraft()) {
			result = null;
			phase = 'form';
			toast.info('Tailored CV discarded.');
			refreshUsage();
		}
		busy = null;
	}

	async function regenerate(next: AiModel) {
		if (!result) return;
		const jobId = result.job.id;
		busy = 'regenerate';
		if (await deleteDraft()) {
			model = next;
			await run(next, jobId);
		}
		busy = null;
	}

	const regenerateItems = $derived(
		result
			? otherModels(result.ai_model, session.aiModels).map((option) => ({
					label: option.plan === 'pro' ? `${option.label} (Pro)` : option.label,
					disabled:
						busy !== null ||
						Boolean(session.usage?.ai_runs.message) ||
						(session.plansEnforced && option.plan === 'pro' && session.me?.plan !== 'pro'),
					onselect: () => void regenerate(option.id)
				}))
			: []
	);

	function useSavedJob(job: JobSummary) {
		savedJob = job;
		error = null;
	}

	async function removeJob() {
		const job = deletingJob;
		if (!job) return;
		try {
			await unwrap(api.DELETE('/api/v1/jobs/{job_id}', { params: { path: { job_id: job.id } } }));
			jobs = jobs.filter((row) => row.id !== job.id);
			if (savedJob?.id === job.id) savedJob = null;
			toast.info('Job deleted. CVs made for it are kept.');
		} catch (failure) {
			toast.error(errorMessage(failure));
		} finally {
			deleteOpen = false;
		}
	}

	function jobLabel(job: JobSummary): string {
		const name = job.title || 'Untitled job';
		return job.company ? `${name} at ${job.company}` : name;
	}
</script>

<Page title="Tailor" width={phase === 'review' ? 'full' : 'narrow'}>
	{#snippet actions()}
		{#if phase === 'review' && result}
			<Button
				variant="ghost"
				loading={busy === 'discard'}
				disabled={busy !== null}
				onclick={discard}
			>
				Discard
			</Button>
			{#if regenerateItems.length > 0}
				<Menu text="Regenerate with" items={regenerateItems} />
			{/if}
			<Button
				variant="primary"
				disabled={busy !== null}
				onclick={() => result && goto(resolve('/app/documents/[id]', { id: result.document.id }))}
			>
				Open in editor
			</Button>
		{/if}
	{/snippet}

	{#if phase === 'review' && result}
		<TailorReview {result} />
	{:else if phase === 'running'}
		<GenerationProgress
			steps={STEPS}
			caption="Tailoring with {model ? modelLabel(model, session.aiModels) : ''}"
			oncancel={() => controller?.abort()}
		/>
	{:else if profiles === null}
		<Card><Skeleton lines={6} /></Card>
	{:else if profiles.length === 0}
		<Card>
			<EmptyState
				icon="profiles"
				title="Start with a profile"
				hint="Tailoring picks from your profile. Import a CV or enter your experience first."
				actionLabel="Import a CV"
				actionIcon="import"
				onaction={() => goto(resolve('/app/profiles/new'))}
			/>
		</Card>
	{:else}
		<form class="flex flex-col gap-6" onsubmit={submit}>
			<Card title="Job">
				{#if savedJob}
					<div class="flex items-center justify-between gap-4">
						<div class="min-w-0">
							<p class="truncate text-base font-medium text-fg">{jobLabel(savedJob)}</p>
							<p class="text-sm text-fg-muted">
								Saved {formatRelative(savedJob.created_at)}. The saved description is used.
							</p>
						</div>
						<Button size="sm" onclick={() => (savedJob = null)}>Use a new description</Button>
					</div>
				{:else}
					<div class="flex flex-col gap-4">
						<Textarea
							label="Job description"
							rows={10}
							required
							maxlength={30000}
							bind:value={description}
							help="Paste the whole ad. It is treated as data, never as instructions."
						/>
						<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
							<Input label="Job title" bind:value={title} help="Optional" maxlength={200} />
							<Input label="Company" bind:value={company} help="Optional" maxlength={200} />
							<Input label="Link to the ad" type="url" bind:value={url} help="Optional" />
						</div>
					</div>
				{/if}
			</Card>

			<Card title="CV">
				<div class="flex flex-col gap-4">
					<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
						<Select
							label="Profile"
							bind:value={profileId}
							options={profiles.map((p) => ({ value: p.id, label: p.name }))}
						/>
						<Select
							label="Template"
							bind:value={templateId}
							options={templates.list.map((t) => ({ value: t.id, label: t.name }))}
						/>
					</div>
					<ModelSelect
						bind:value={model}
						models={session.aiModels}
						plan={session.me?.plan}
						enforced={session.plansEnforced}
					/>
					{#if error}
						<p class="text-sm text-danger" role="alert">{error}</p>
					{/if}
					{#if blocked}
						<!-- Next to the button it disables, so the reason is where the user looks. -->
						<LimitNotice
							id="tailor-blocked"
							message={blocked}
							upgrade={canUpgrade(session.usage, session.billingEnabled)}
						/>
					{/if}
					<div>
						<Button
							type="submit"
							variant="primary"
							icon="tailor"
							disabled={!ready}
							aria-describedby={blocked ? 'tailor-blocked' : undefined}
						>
							Tailor CV
						</Button>
					</div>
				</div>
			</Card>
		</form>

		{#if jobs.length > 0}
			<Card title="Saved jobs" padding="none">
				<ul>
					{#each jobs as job (job.id)}
						<li class="flex h-12 items-center gap-3 border-t border-line px-5">
							<p class="min-w-0 flex-1 truncate text-base text-fg">{jobLabel(job)}</p>
							<span class="hidden text-sm text-fg-muted sm:inline">
								{formatRelative(job.created_at)}
							</span>
							<Button size="sm" onclick={() => useSavedJob(job)}>Tailor again</Button>
							<IconButton
								label="Delete {jobLabel(job)}"
								icon="delete"
								onclick={() => {
									deletingJob = job;
									deleteOpen = true;
								}}
							/>
						</li>
					{/each}
				</ul>
			</Card>
		{/if}
	{/if}
</Page>

<ConfirmDialog
	bind:open={deleteOpen}
	title="Delete this job?"
	message="{deletingJob
		? jobLabel(deletingJob)
		: 'The job'} will be deleted. CVs you made for it are kept."
	confirmLabel="Delete job"
	danger
	onconfirm={removeJob}
/>
