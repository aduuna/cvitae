<script lang="ts">
	import Badge from '@web/components/ui/Badge.svelte';
	import Button from '@web/components/ui/Button.svelte';
	import Card from '@web/components/ui/Card.svelte';
	import Checkbox from '@web/components/ui/Checkbox.svelte';
	import Icon from '@web/components/ui/Icon.svelte';
	import IconButton from '@web/components/ui/IconButton.svelte';
	import Textarea from '@web/components/ui/Textarea.svelte';
	import { toast } from '@web/components/ui/toasts.svelte.ts';
	import { answerNotes, contextText, countText, hintText, limitText } from './answers.ts';
	import type { Panel } from './panel.svelte.ts';
	import { plural } from './review.ts';

	let { panel }: { panel: Panel } = $props();

	const step = $derived(panel.answerStep);
	const source = $derived(panel.sourceLabel || 'profile');
	const noun = $derived(panel.source?.kind === 'document' ? 'CV' : 'profile');
	const toDraft = $derived(panel.questions.filter((row) => row.draft).length);
	const drafted = $derived(panel.questions.filter((row) => row.answer));
	const toFill = $derived(
		drafted.filter((row) => row.answer?.fill && row.answer.text.trim()).length
	);
	const notes = $derived(answerNotes(panel.questions));

	async function undo() {
		const restored = await panel.undoAnswers();
		toast.info(`Put back ${plural(restored, 'field')}.`);
	}
</script>

{#snippet problem()}
	{#if panel.answerProblem}
		<p class="text-sm text-danger" role="alert">{panel.answerProblem.message}</p>
		{#if panel.answerProblem.settings}
			<div>
				<Button size="sm" onclick={() => panel.openApp('/app/settings')}>Open settings</Button>
			</div>
		{/if}
	{/if}
{/snippet}

{#snippet policy()}
	{#if panel.aiPolicy}
		<div class="flex gap-2 rounded-md border border-line bg-subtle p-3">
			<span class="pt-0.5 text-fg-muted"><Icon name="placeholder-warning" /></span>
			<div class="flex min-w-0 flex-col gap-1">
				<p class="text-sm text-fg">This application asks applicants not to use AI.</p>
				<p class="text-sm text-fg-muted">"{panel.aiPolicy}"</p>
			</div>
		</div>
	{/if}
{/snippet}

{#if panel.access === 'yes'}
	<Card title="Answer questions">
		<div class="flex flex-col gap-3" aria-live="polite">
			{#if step === 'questions' || step === 'drafting'}
				{@render policy()}
				<p class="text-sm text-fg-muted">{contextText(source, panel.jobContext)}</p>
				<div class="flex flex-col gap-3">
					{#each panel.questions as row (row.key)}
						<Checkbox bind:checked={row.draft} disabled={step === 'drafting'}>
							<span class="flex flex-wrap items-center gap-1.5">
								{row.question.label}
								{#if limitText(row.question)}
									<span class="text-xs text-fg-muted">{limitText(row.question)}</span>
								{/if}
								{#if row.question.filled}<Badge variant="outline">Has a value</Badge>{/if}
							</span>
						</Checkbox>
					{/each}
				</div>
				{@render problem()}
				{#if step === 'drafting'}
					<p class="text-sm text-fg-muted">
						Drafting {plural(toDraft, 'answer')}. This can take up to a minute.
					</p>
				{/if}
				<div class="flex justify-end">
					<Button
						variant="primary"
						icon="ai-draft"
						loading={step === 'drafting'}
						disabled={toDraft === 0 || !panel.source}
						onclick={() => panel.draftAnswers()}
					>
						Draft {plural(toDraft, 'answer')}
					</Button>
				</div>
			{:else if step === 'drafts' || step === 'filling'}
				{@render policy()}
				{#each drafted as row (row.key)}
					{#if row.answer}
						{@const answer = row.answer}
						{@const count = countText(answer.text, row.question)}
						{@const hint = hintText(answer.inferred, noun)}
						<section class="flex flex-col gap-1.5">
							<div class="flex items-start gap-2">
								<div class="min-w-0 flex-1">
									<Checkbox bind:checked={answer.fill} disabled={!answer.text.trim()}>
										<span class="flex flex-wrap items-center gap-1.5">
											{row.question.label}
											{#if row.question.filled}<Badge variant="outline">Has a value</Badge>{/if}
											{#if answer.shortened}<Badge variant="outline">Shortened</Badge>{/if}
										</span>
									</Checkbox>
								</div>
								<IconButton
									size="sm"
									icon="redraft"
									label="Redraft this answer"
									disabled={panel.redrafting !== null || step === 'filling'}
									onclick={() => panel.redraft(row.key)}
								/>
							</div>
							<div class="flex flex-col gap-1 pl-6">
								{#if panel.redrafting === row.key}
									<p class="text-sm text-fg-muted">Redrafting this answer.</p>
								{:else if !answer.text.trim()}
									<p class="text-sm text-fg-muted">Not drafted. Answer this one yourself.</p>
								{/if}
								<Textarea
									bind:value={answer.text}
									rows={row.question.multiline ? 4 : 1}
									aria-label="Answer to {row.question.label}"
									disabled={panel.redrafting === row.key}
								/>
								<p class="text-xs tabular-nums {count.over ? 'text-danger' : 'text-fg-muted'}">
									{count.text}
								</p>
								{#if hint}<p class="text-xs text-fg-muted">{hint}</p>{/if}
							</div>
						</section>
					{/if}
				{/each}
				{#each notes as note (note)}
					<p class="text-sm text-fg">{note}</p>
				{/each}
				<p class="text-sm text-fg-muted">
					Drafted with {panel.answersModel}. Check every answer before you fill it.
				</p>
				{@render problem()}
				<div class="flex justify-end gap-2">
					<Button variant="ghost" onclick={() => panel.cancelDrafts()}>Cancel</Button>
					<Button
						variant="primary"
						loading={step === 'filling'}
						disabled={toFill === 0 || panel.redrafting !== null}
						onclick={() => panel.fillAnswers()}
					>
						Fill {plural(toFill, 'answer')}
					</Button>
				</div>
			{:else if step === 'filled'}
				<p class="text-base text-fg">
					Filled {plural(panel.answersFilled, 'answer')}. Check each one in the page before you
					submit.
				</p>
				<div class="flex gap-2">
					<Button icon="undo" onclick={undo}>Undo</Button>
					<Button onclick={() => panel.editAnswers()}>Edit answers</Button>
				</div>
			{:else}
				<p class="text-sm text-fg-muted">
					Draft answers to the form's open questions from your {source}. You edit them before
					anything goes into the page.
				</p>
				{#if step === 'none'}
					<p class="text-sm text-fg">
						No open questions on this page. If the form has steps, go to the step with the
						questions.
					</p>
				{/if}
				{@render problem()}
				<div>
					<Button loading={step === 'finding'} onclick={() => panel.findQuestions()}>
						Find questions
					</Button>
				</div>
			{/if}
		</div>
	</Card>
{/if}
