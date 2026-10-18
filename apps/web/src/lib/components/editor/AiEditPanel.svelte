<script lang="ts" module>
	const OPEN_KEY = 'vitae.editor.aiPanel';

	/** Whether the user left the panel open; storage can be unavailable (private mode). */
	function loadOpen(): boolean {
		try {
			return localStorage.getItem(OPEN_KEY) === 'open';
		} catch {
			return false;
		}
	}

	function saveOpen(open: boolean): void {
		try {
			localStorage.setItem(OPEN_KEY, open ? 'open' : 'closed');
		} catch {
			// Not persisted; the panel still opens for this visit.
		}
	}
</script>

<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { scopeOptions, WHOLE_CV, type AiEditChat } from '#lib/ai/edit.svelte.ts';
	import { modelLabel, modelOptions, pickModel } from '#lib/ai/models.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import { canUpgrade } from '#lib/billing/plans.ts';
	import LimitNotice from '#lib/components/billing/LimitNotice.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import Select from '#lib/components/ui/Select.svelte';
	import Textarea from '#lib/components/ui/Textarea.svelte';
	import type { AiModel, CvContent } from '#lib/cv/types.ts';

	interface Props {
		chat: AiEditChat;
		/** The form's content: the part picker lists its sections. */
		content: CvContent;
	}

	let { chat, content }: Props = $props();

	let open = $state(loadOpen());
	let draft = $state('');
	let scope = $state(WHOLE_CV);
	let model = $state<AiModel | null>(null);
	let input: HTMLTextAreaElement | undefined = $state();
	let log: HTMLDivElement | undefined = $state();

	const panelId = $props.id();
	const hintId = `${panelId}-hint`;
	const scopes = $derived(scopeOptions(content));
	// A part that is no longer in the CV falls back to the whole CV.
	const scopeValue = $derived(scopes.some((option) => option.value === scope) ? scope : WHOLE_CV);
	const models = $derived(
		modelOptions(session.aiModels, {
			plan: session.me?.plan ?? 'free',
			enforced: session.plansEnforced
		})
	);
	const limit = $derived(session.usage?.ai_runs.message ?? null);
	const ready = $derived(draft.trim() !== '' && model !== null && limit === null && !chat.pending);

	onMount(() => {
		const fallback = () => pickModel(null, session.aiModels, session.defaultAiModel);
		session.loadMe().then(
			(me) =>
				(model ??= pickModel(me.preferred_ai_model, session.aiModels, session.defaultAiModel)),
			() => (model ??= fallback())
		);
		session.loadUsage().catch(() => {});
	});

	// Keep the newest message in view.
	$effect(() => {
		void chat.messages.length;
		void chat.pending;
		if (log) log.scrollTop = log.scrollHeight;
	});

	function scopeLabel(value: string | null): string | null {
		if (value === null) return null;
		return scopes.find((option) => option.value === value)?.label ?? null;
	}

	async function toggle() {
		open = !open;
		saveOpen(open);
		if (open) {
			await tick();
			input?.focus();
		}
	}

	async function submit(event?: SubmitEvent) {
		event?.preventDefault();
		if (!ready) return;
		const text = draft;
		draft = '';
		const sent = await chat.send(text, { scope: scopeValue || null, model });
		// Give the text back when nothing came of it, unless the user started a new one.
		if (!sent && !draft) draft = text;
		session.refreshUsage().catch(() => {});
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
			event.preventDefault();
			void submit();
		}
	}
</script>

<section class="flex shrink-0 flex-col border-t border-line bg-surface" aria-label="Edit with AI">
	{#if open}
		<button
			type="button"
			class="flex h-10 w-full shrink-0 items-center gap-2 px-4 text-left text-fg transition-colors duration-120 ease-out hover:bg-subtle"
			aria-expanded="true"
			aria-controls={panelId}
			aria-label="Edit with AI"
			onclick={toggle}
		>
			<Icon name="ai-edit" />
			<span class="text-base font-medium">Edit with AI</span>
			<span class="ml-auto text-fg-muted"><Icon name="chevron-down" /></span>
		</button>
	{:else}
		<div class="flex items-center gap-3 p-3">
			<button
				type="button"
				class="inline-flex h-8 shrink-0 items-center gap-2 rounded-full bg-accent px-3.5 text-base font-medium text-accent-fg transition-colors duration-120 ease-out select-none hover:bg-accent/85 active:bg-accent/75"
				aria-expanded="false"
				aria-controls={panelId}
				aria-label="Edit with AI"
				aria-describedby={chat.pending ? undefined : hintId}
				onclick={toggle}
			>
				<Icon name="ai-edit" />
				Edit with AI
			</button>
			{#if chat.pending}
				<span class="flex items-center gap-1.5 text-sm text-fg-muted">
					<Icon name="loading" spin />Working
				</span>
			{:else}
				<span id={hintId} class="truncate text-sm text-fg-muted">
					Ask for a change in plain words
				</span>
			{/if}
		</div>
	{/if}

	{#if open}
		<div id={panelId} class="flex flex-col border-t border-line">
			<div
				bind:this={log}
				role="log"
				aria-label="Conversation"
				class="flex max-h-72 min-h-16 flex-col gap-3 overflow-y-auto px-4 py-3"
			>
				{#if chat.messages.length === 0 && !chat.pending}
					<p class="text-sm text-fg-muted">
						Ask for a change, such as "Shorten the summary to two sentences". To change one part
						only, pick it below. Edits keep to what this CV already says; anything new comes back
						highlighted for you to check.
					</p>
				{/if}
				{#each chat.messages as message (message.id)}
					{#if message.role === 'user'}
						{@const label = scopeLabel(message.scope)}
						<div class="flex flex-col items-end gap-1">
							{#if label}<span class="text-xs font-medium text-fg-muted">{label}</span>{/if}
							<p
								class="max-w-[85%] rounded-lg bg-muted px-3 py-2 text-base whitespace-pre-wrap text-fg"
							>
								{message.text}
							</p>
						</div>
					{:else if message.role === 'assistant'}
						<div class="flex flex-col gap-1.5">
							<p class="text-base whitespace-pre-wrap text-fg">{message.text}</p>
							{#if message.issues.length > 0}
								<ul class="flex flex-col gap-1" aria-label="Checked against your CV">
									{#each message.issues as issue, index (index)}
										<li class="flex gap-2 text-sm text-fg-muted">
											<span class="mt-px"><Icon name="placeholder-warning" /></span>
											<span>{issue.message}</span>
										</li>
									{/each}
								</ul>
							{/if}
							<div class="flex min-h-7 flex-wrap items-center gap-x-2 text-sm text-fg-muted">
								{#if !message.edit}
									<span>No change made.</span>
								{:else if message.edit.status === 'stale'}
									<span>You edited the CV while this ran, so the change is not applied.</span>
									{#if chat.canApply(message)}
										<Button size="sm" onclick={() => chat.applyAnyway(message)}>Apply anyway</Button
										>
									{/if}
								{:else if message.edit.status === 'undone'}
									<span>Undone.</span>
								{:else}
									<span>Edited with {modelLabel(message.model, session.aiModels)}.</span>
									{#if chat.canUndo(message)}
										<Button
											size="sm"
											variant="ghost"
											icon="undo"
											onclick={() => chat.undo(message)}
										>
											Undo
										</Button>
									{/if}
								{/if}
							</div>
						</div>
					{:else}
						<p class="text-sm text-danger">{message.text}</p>
					{/if}
				{/each}
				{#if chat.pending}
					<p class="flex items-center gap-2 text-sm text-fg-muted">
						<Icon name="loading" spin />Editing the CV
					</p>
				{/if}
			</div>

			{#if session.aiModels.length === 0}
				<p class="border-t border-line px-4 py-3 text-sm text-fg-muted">
					AI is not set up on this server yet.
				</p>
			{:else}
				{#if limit}
					<div class="border-t border-line p-3">
						<LimitNotice
							message={limit}
							upgrade={canUpgrade(session.usage, session.billingEnabled)}
						/>
					</div>
				{/if}
				<form class="flex flex-col gap-2 border-t border-line p-3" onsubmit={submit}>
					<div class="flex gap-2">
						<div class="min-w-0 flex-1">
							<Select
								aria-label="Part to change"
								options={scopes}
								bind:value={() => scopeValue, (next) => (scope = next)}
							/>
						</div>
						<div class="min-w-0 flex-1">
							<Select
								aria-label="AI model"
								options={models}
								bind:value={() => model ?? '', (next) => (model = next as AiModel)}
							/>
						</div>
					</div>
					<div class="flex items-end gap-2">
						<div class="min-w-0 flex-1">
							<Textarea
								bind:ref={input}
								bind:value={draft}
								rows={2}
								aria-label="Change to make"
								placeholder="Describe a change, for example: lead each bullet with a verb"
								disabled={limit !== null}
								{onkeydown}
							/>
						</div>
						{#if chat.pending}
							<Button onclick={() => chat.stop()}>Stop</Button>
						{:else}
							<Button type="submit" variant="primary" icon="send" disabled={!ready}>Send</Button>
						{/if}
					</div>
				</form>
			{/if}
		</div>
	{/if}
</section>
