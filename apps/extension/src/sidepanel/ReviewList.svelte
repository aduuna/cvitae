<script lang="ts">
	import Badge from '@web/components/ui/Badge.svelte';
	import Checkbox from '@web/components/ui/Checkbox.svelte';
	import Input from '@web/components/ui/Input.svelte';
	import Textarea from '@web/components/ui/Textarea.svelte';
	import type { Panel } from './panel.svelte.ts';
	import { grouped, type Row } from './review.ts';

	let { panel, rows, notes }: { panel: Panel; rows: Row[]; notes: string[] } = $props();

	// The scan loads the data; section titles name the role or school each row comes from.
	const groups = $derived(panel.details ? grouped(rows, panel.details) : [{ title: '', rows }]);
</script>

<div class="flex flex-col gap-4">
	<p class="text-sm text-fg-muted">
		Check what goes where. Untick a field to leave it, or change its text first.
	</p>
	{#each notes as note (note)}
		<p class="text-sm text-fg">{note}</p>
	{/each}
	{#each groups as group (group.title)}
		<section class="flex flex-col gap-3">
			{#if group.title}
				<h2 class="text-sm font-medium text-fg-muted">{group.title}</h2>
			{/if}
			{#each group.rows as row (row.frameId + row.fieldId)}
				<div class="flex flex-col gap-1.5">
					<Checkbox bind:checked={row.include}>
						<span class="flex flex-wrap items-center gap-1.5">
							{row.label || 'Field'}
							{#if row.filled}<Badge variant="outline">Has a value</Badge>{/if}
							{#if row.needsChoice}<Badge variant="outline">Pick from list</Badge>{/if}
							{#if row.shortened}<Badge variant="outline">Shortened</Badge>{/if}
						</span>
					</Checkbox>
					<div class="pl-6">
						{#if row.editable && row.long}
							<Textarea
								bind:value={row.value}
								rows={4}
								aria-label="Text for {row.label}"
								disabled={!row.include}
							/>
						{:else if row.editable}
							<Input
								bind:value={row.value}
								aria-label="Text for {row.label}"
								disabled={!row.include}
							/>
						{:else}
							<p class="text-sm text-fg">{row.display}</p>
						{/if}
					</div>
				</div>
			{/each}
		</section>
	{/each}
</div>
