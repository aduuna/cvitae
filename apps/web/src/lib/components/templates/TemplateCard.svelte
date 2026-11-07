<script lang="ts">
	import Badge from '#lib/components/ui/Badge.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Menu, { type MenuItem } from '#lib/components/ui/Menu.svelte';
	import type { TemplateMeta } from '#lib/cv/types.ts';
	import { svgDataUrl } from '#lib/preview.svelte.ts';

	interface Props {
		template: TemplateMeta;
		/** The first page as SVG; undefined while it renders, null when it could not be. */
		preview: string | null | undefined;
		isDefault: boolean;
		/** True while a default is being saved, for this card or another. */
		busy: boolean;
		/** True while this card's default is being saved. */
		saving: boolean;
		onmakedefault: () => void;
		/** Rename, view source and delete: only for the user's own templates. */
		menu?: MenuItem[];
	}

	let { template, preview, isDefault, busy, saving, onmakedefault, menu }: Props = $props();
</script>

<li class="flex flex-col rounded-lg border border-line bg-surface" data-template={template.id}>
	<div class="flex justify-center rounded-t-lg border-b border-line bg-canvas p-6">
		{#if preview}
			<img
				src={svgDataUrl(preview)}
				alt="Preview of the {template.name} template"
				class="aspect-[210/297] w-full max-w-72 bg-paper shadow-page"
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
			<h3 class="min-w-0 truncate text-lg font-semibold text-fg">{template.name}</h3>
			{#if isDefault}
				<Badge>Default</Badge>
			{/if}
			{#if menu}
				<div class="-mr-1 ml-auto">
					<Menu label="Actions for {template.name}" items={menu} />
				</div>
			{/if}
		</div>
		<p class="flex-1 text-sm text-fg-muted">{template.description}</p>
		{#if !isDefault}
			<div>
				<Button size="sm" loading={saving} disabled={busy} onclick={onmakedefault}>
					Set as default
				</Button>
			</div>
		{/if}
	</div>
</li>
