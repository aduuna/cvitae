<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import Page from '#lib/components/shell/Page.svelte';
	import Badge from '#lib/components/ui/Badge.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import { svgDataUrl } from '#lib/preview.svelte.ts';
	import { DEFAULT_TEMPLATE_ID, templates } from '#lib/templates.svelte.ts';

	let previews = $state<Record<string, string | null>>({});
	let loadError = $state<string | null>(null);
	let saving = $state<string | null>(null);

	const defaultId = $derived(session.me?.default_template_id ?? DEFAULT_TEMPLATE_ID);

	async function loadPreview(id: string) {
		try {
			const pages = await unwrap(
				api.GET('/api/v1/templates/{template_id}/preview', {
					params: { path: { template_id: id } }
				})
			);
			previews[id] = pages.pages[0] ?? null;
		} catch {
			previews[id] = null;
		}
	}

	onMount(async () => {
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
</script>

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
		<ul class="grid grid-cols-2 gap-6">
			{#each templates.list as template (template.id)}
				{@const preview = previews[template.id]}
				{@const isDefault = template.id === defaultId}
				<li class="flex flex-col overflow-hidden rounded-lg border border-line bg-surface">
					<div class="flex justify-center border-b border-line bg-canvas p-6">
						{#if preview}
							<img
								src={svgDataUrl(preview)}
								alt="Preview of the {template.name} template"
								class="aspect-[210/297] w-full max-w-72 bg-surface shadow-page"
							/>
						{:else if preview === null}
							<div
								class="flex aspect-[210/297] w-full max-w-72 items-center justify-center bg-surface p-4 text-center text-sm text-fg-muted shadow-page"
							>
								The preview could not be rendered.
							</div>
						{:else}
							<div
								class="aspect-[210/297] w-full max-w-72 animate-pulse bg-surface shadow-page"
								aria-hidden="true"
							></div>
						{/if}
					</div>
					<div class="flex flex-1 flex-col gap-3 p-4">
						<div class="flex items-center gap-2">
							<h2 class="text-lg font-semibold text-fg">{template.name}</h2>
							{#if isDefault}
								<Badge>Default</Badge>
							{/if}
						</div>
						<p class="flex-1 text-sm text-fg-muted">{template.description}</p>
						{#if !isDefault}
							<div>
								<Button
									size="sm"
									loading={saving === template.id}
									disabled={saving !== null}
									onclick={() => makeDefault(template.id)}
								>
									Set as default
								</Button>
							</div>
						{/if}
					</div>
				</li>
			{/each}
		</ul>
	{/if}
</Page>
