<script lang="ts">
	import Button from '@web/components/ui/Button.svelte';
	import Card from '@web/components/ui/Card.svelte';
	import { toast } from '@web/components/ui/toasts.svelte.ts';
	import type { Panel } from './panel.svelte.ts';
	import { plural } from './review.ts';
	import ReviewList from './ReviewList.svelte';

	let { panel }: { panel: Panel } = $props();

	const fill = $derived(panel.fill);
	const ticked = $derived(fill.step === 'review' ? fill.rows.filter((r) => r.include).length : 0);
	const where = $derived(
		panel.site && panel.host ? `${panel.site} form on ${panel.host}` : (panel.host ?? 'This page')
	);

	async function undo() {
		const restored = await panel.undo();
		toast.info(`Put back ${plural(restored, 'field')}.`);
	}
</script>

<Card title="Fill this application">
	<div class="flex flex-col gap-3" aria-live="polite">
		{#if panel.access === 'unsupported'}
			<p class="text-sm text-fg-muted">The extension cannot work on this page.</p>
		{:else if panel.access === 'no'}
			<p class="text-sm text-fg-muted">
				To use it on this page, click the Chameleon vitae button in the browser's toolbar while the
				page is open.
			</p>
		{:else if fill.step === 'review'}
			<ReviewList {panel} rows={fill.rows} notes={fill.notes} />
			<div class="flex justify-end gap-2">
				<Button variant="ghost" onclick={() => (panel.fill = { step: 'idle' })}>Cancel</Button>
				<Button variant="primary" disabled={ticked === 0} onclick={() => panel.confirmFill()}>
					Fill {plural(ticked, 'field')}
				</Button>
			</div>
		{:else if fill.step === 'done'}
			<p class="text-base text-fg">
				Filled {plural(fill.count, 'field')}. Check each one in the page before you submit.
			</p>
			{#each fill.notes as note (note)}
				<p class="text-sm text-fg-muted">{note}</p>
			{/each}
			<div class="flex gap-2">
				<Button onclick={undo}>Undo fill</Button>
				<Button onclick={() => panel.scanForm()}>Fill again</Button>
			</div>
		{:else}
			<p class="text-sm text-fg-muted">
				{where}. The extension fills fields in the page and never submits it.
			</p>
			{#if fill.step === 'empty'}
				<p class="text-sm text-fg">
					No fields on this page match your profile. If the form has steps, go to the step that asks
					for your details.
				</p>
			{:else if fill.step === 'error'}
				<p class="text-sm text-danger" role="alert">{fill.message}</p>
			{/if}
			<div>
				<Button
					variant="primary"
					icon="form"
					loading={fill.step === 'scanning' || fill.step === 'filling'}
					disabled={!panel.source}
					onclick={() => panel.scanForm()}
				>
					Fill form
				</Button>
			</div>
		{/if}

		{#if panel.access === 'yes' && panel.files.length > 0}
			<div class="flex flex-col gap-2 border-t border-line pt-3">
				<p class="text-sm font-medium text-fg">CV upload</p>
				{#if panel.source?.kind !== 'document'}
					<p class="text-sm text-fg-muted">
						To attach a CV as a PDF, choose one of your CVs under Fill from.
					</p>
				{:else if panel.attach.step === 'attached'}
					<p class="text-sm text-fg">Attached {panel.attach.name}.</p>
				{:else}
					{#each panel.files as target (target.field.id)}
						<div>
							<Button
								icon="file"
								loading={panel.attach.step === 'working'}
								onclick={() => panel.attachCv(target)}
							>
								Attach CV{panel.files.length > 1 ? ` to ${target.field.label}` : ''}
							</Button>
						</div>
					{/each}
					{#if panel.attach.step === 'placeholders'}
						<p class="text-sm text-danger" role="alert">
							This CV still has {panel.attach.count}
							{panel.attach.count === 1 ? 'placeholder' : 'placeholders'}. Fill them in the editor
							before you send it.
						</p>
						<div>
							<Button
								size="sm"
								onclick={() => panel.source && panel.openApp(`/app/documents/${panel.source.id}`)}
							>
								Open in editor
							</Button>
						</div>
					{:else if panel.attach.step === 'error'}
						<p class="text-sm text-danger" role="alert">{panel.attach.message}</p>
					{/if}
				{/if}
			</div>
		{/if}

		{#if panel.access === 'yes' && !panel.siteAllowed && panel.host}
			<div class="flex flex-col gap-2 border-t border-line pt-3">
				<p class="text-sm text-fg-muted">
					Allow {panel.host} to have the extension offer to fill forms there without the toolbar button.
				</p>
				<div>
					<Button size="sm" onclick={() => panel.allowThisSite()}>Allow on this site</Button>
				</div>
			</div>
		{/if}
	</div>
</Card>
