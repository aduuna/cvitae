<script lang="ts">
	import { onMount } from 'svelte';
	import { errorMessage } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import { canUpgrade } from '#lib/billing/plans.ts';
	import LimitNotice from '#lib/components/billing/LimitNotice.svelte';
	import Page from '#lib/components/shell/Page.svelte';
	import AddTemplateDialog from '#lib/components/templates/AddTemplateDialog.svelte';
	import TemplateCard from '#lib/components/templates/TemplateCard.svelte';
	import TemplateSourceDialog from '#lib/components/templates/TemplateSourceDialog.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';
	import Dialog from '#lib/components/ui/Dialog.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import type { MenuItem } from '#lib/components/ui/Menu.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import {
		canMakeTemplates,
		deleteTemplate,
		loadTemplatePreview,
		NAME_MAX,
		renameTemplate,
		templatesBlocked
	} from '#lib/custom-templates.ts';
	import type { CustomTemplate, TemplateMeta } from '#lib/cv/types.ts';
	import { DEFAULT_TEMPLATE_ID, templates } from '#lib/templates.svelte.ts';

	let previews = $state<Record<string, string | null>>({});
	let loadError = $state<string | null>(null);
	let saving = $state<string | null>(null);

	let addOpen = $state(false);
	let viewOpen = $state(false);
	let viewing = $state<TemplateMeta | null>(null);
	let renameOpen = $state(false);
	let renaming = $state<TemplateMeta | null>(null);
	let renameValue = $state('');
	let renameSaving = $state(false);
	let deleteOpen = $state(false);
	let deleting = $state<TemplateMeta | null>(null);

	const defaultId = $derived(session.me?.default_template_id ?? DEFAULT_TEMPLATE_ID);
	/** Templates always run on Claude: without a Claude model there is nothing to offer. */
	const canMake = $derived(canMakeTemplates(session.aiModels));
	const showOwn = $derived(canMake || templates.custom.length > 0);
	const blocked = $derived(templatesBlocked(session.usage));

	async function loadPreview(id: string) {
		try {
			previews[id] = await loadTemplatePreview(id);
		} catch {
			previews[id] = null;
		}
	}

	onMount(async () => {
		session.loadUsage().catch(() => {});
		try {
			await Promise.all([templates.load(), session.loadMe()]);
		} catch (error) {
			loadError = errorMessage(error);
			return;
		}
		for (const template of templates.list) void loadPreview(template.id);
	});

	async function makeDefault(id: string) {
		saving = id;
		try {
			await session.updateMe({ default_template_id: id });
			toast.info(`New CVs now use ${templates.name(id)}.`);
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			saving = null;
		}
	}

	async function saved(template: CustomTemplate, page: string | null) {
		if (page) previews[template.id] = page;
		else void loadPreview(template.id);
		toast.info('Template saved.');
		try {
			await templates.refresh();
		} catch {
			toast.error('Templates could not reload. Reload the page to see the new one.');
		}
		session.refreshUsage().catch(() => {});
	}

	function menuFor(template: TemplateMeta): MenuItem[] {
		return [
			{
				label: 'Rename',
				icon: 'rename',
				onselect: () => {
					renaming = template;
					renameValue = template.name;
					renameOpen = true;
				}
			},
			{
				label: 'View source',
				icon: 'view-source',
				onselect: () => {
					viewing = template;
					viewOpen = true;
				}
			},
			{
				label: 'Delete',
				icon: 'delete',
				danger: true,
				onselect: () => {
					deleting = template;
					deleteOpen = true;
				}
			}
		];
	}

	async function rename(event: SubmitEvent) {
		event.preventDefault();
		const name = renameValue.trim();
		if (!renaming || !name) return;
		renameSaving = true;
		try {
			await renameTemplate(renaming.id, name);
			await templates.refresh();
			renameOpen = false;
			toast.info('Template renamed.');
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			renameSaving = false;
		}
	}

	async function remove() {
		if (!deleting) return;
		const id = deleting.id;
		try {
			await deleteTemplate(id);
		} catch (error) {
			toast.error(errorMessage(error));
			return;
		}
		delete previews[id];
		templates.list = templates.list.filter((template) => template.id !== id);
		toast.info('Template deleted.');
		// CVs and the default may have switched to another template, and there is room again.
		templates.refresh().catch(() => {});
		session.refreshMe().catch(() => {});
		session.refreshUsage().catch(() => {});
	}
</script>

{#snippet card(template: TemplateMeta)}
	<TemplateCard
		{template}
		preview={previews[template.id]}
		isDefault={template.id === defaultId}
		busy={saving !== null}
		saving={saving === template.id}
		onmakedefault={() => makeDefault(template.id)}
		menu={template.custom ? menuFor(template) : undefined}
	/>
{/snippet}

<Page title="Templates">
	<p class="text-sm text-fg-muted">
		Previews show your default profile, or sample data until you have one. New CVs use the default
		template; you can switch any CV later.
	</p>

	{#if loadError}
		<p class="text-sm text-danger" role="alert">{loadError}</p>
	{:else if templates.list.length === 0}
		<div class="grid grid-cols-2 gap-6">
			<Skeleton variant="block" height="lg" />
			<Skeleton variant="block" height="lg" />
		</div>
	{:else}
		<section class="flex flex-col gap-3" aria-labelledby="built-in-templates">
			<h2 id="built-in-templates" class="text-lg font-semibold text-fg">Built-in templates</h2>
			<ul class="grid grid-cols-2 gap-6">
				{#each templates.builtIn as template (template.id)}
					{@render card(template)}
				{/each}
			</ul>
		</section>

		{#if showOwn}
			<section class="flex flex-col gap-3" aria-labelledby="your-templates">
				<div class="flex flex-col gap-1">
					<h2 id="your-templates" class="text-lg font-semibold text-fg">Your templates</h2>
					<p class="text-sm text-fg-muted">
						Made from the look of a CV you like. Only you can see and use them.
					</p>
				</div>
				{#if blocked && canMake}
					<LimitNotice
						id="template-blocked"
						message={blocked}
						upgrade={canUpgrade(session.usage, session.billingEnabled)}
					/>
				{/if}
				<ul class="grid grid-cols-2 gap-6">
					{#each templates.custom as template (template.id)}
						{@render card(template)}
					{/each}
					{#if canMake}
						<li class="flex">
							<button
								type="button"
								disabled={blocked !== null}
								aria-describedby={blocked ? 'template-blocked' : undefined}
								onclick={() => (addOpen = true)}
								class="flex min-h-64 w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line-strong bg-surface p-6 text-center transition-colors duration-120 ease-out enabled:hover:border-fg-muted enabled:hover:bg-subtle disabled:cursor-not-allowed disabled:opacity-40"
							>
								<span class="text-fg-muted"><Icon name="new" /></span>
								<span class="text-lg font-semibold text-fg">Add your own</span>
								<span class="max-w-60 text-sm text-fg-muted">
									Upload a CV whose design you like and use its look for your own CVs.
								</span>
							</button>
						</li>
					{/if}
				</ul>
			</section>
		{/if}
	{/if}
</Page>

{#if addOpen}
	<AddTemplateDialog onsaved={saved} onclose={() => (addOpen = false)} />
{/if}

<TemplateSourceDialog bind:open={viewOpen} template={viewing} />

<Dialog bind:open={renameOpen} title="Rename template">
	<form id="rename-template" onsubmit={rename}>
		<Input
			label="Name"
			bind:value={renameValue}
			maxlength={NAME_MAX}
			error={renameValue.trim() ? undefined : 'Give the template a name.'}
		/>
	</form>
	{#snippet footer()}
		<Button onclick={() => (renameOpen = false)}>Cancel</Button>
		<Button
			variant="primary"
			type="submit"
			form="rename-template"
			loading={renameSaving}
			disabled={!renameValue.trim()}
		>
			Rename template
		</Button>
	{/snippet}
</Dialog>

<ConfirmDialog
	bind:open={deleteOpen}
	title="Delete template"
	message="{deleting?.name ??
		'This template'} will be deleted. CVs that use it switch to your default template, or to Classic if this is your default."
	confirmLabel="Delete template"
	danger
	onconfirm={remove}
/>
