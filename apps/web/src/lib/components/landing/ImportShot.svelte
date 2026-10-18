<script lang="ts">
	import Icon from '#lib/components/ui/Icon.svelte';
	import Shot from './Shot.svelte';

	const sections = [
		['Experience', '3 roles'],
		['Projects', '1'],
		['Education', '1'],
		['Skills', '3 groups'],
		['Certifications', '2']
	] as const;
</script>

<Shot label="Importing a CV: the uploaded PDF, and the sections read from it, waiting for review.">
	<div class="flex flex-col gap-3">
		<div class="rounded-lg border border-line bg-surface p-4">
			<div class="flex gap-4 border-b border-line text-base">
				<span
					class="-mb-px inline-flex h-9 items-center border-b-2 border-accent font-medium text-fg"
				>
					Upload a CV
				</span>
				<span class="inline-flex h-9 items-center text-fg-muted">Paste a CV</span>
				<span class="hidden h-9 items-center text-fg-muted sm:inline-flex">Enter manually</span>
			</div>
			<div
				class="mt-4 flex items-center gap-3 rounded-md border border-dashed border-line-strong px-4 py-3"
			>
				<span class="flex size-8 items-center justify-center rounded-md bg-muted text-fg-muted">
					<Icon name="file" />
				</span>
				<span class="flex min-w-0 flex-col">
					<span class="truncate font-mono text-sm text-fg">ama-owusu-mensah-cv.pdf</span>
					<span class="font-mono text-xs text-fg-muted">182 KB</span>
				</span>
				<span class="ml-auto text-fg"><Icon name="check" /></span>
			</div>
			<p class="mt-3 text-sm text-fg-muted">Extracted with Claude Haiku</p>
		</div>

		<div class="rounded-lg border border-line bg-surface">
			<p class="border-b border-line px-4 py-3 text-sm text-fg-muted">
				Imported from ama-owusu-mensah-cv.pdf. Check every entry before using it.
			</p>
			<ul class="flex flex-col divide-y divide-line">
				{#each sections as [name, count] (name)}
					<li class="flex h-10 items-center justify-between px-4 text-base text-fg">
						{name}
						<span class="text-sm text-fg-muted tabular-nums">{count}</span>
					</li>
				{/each}
			</ul>
		</div>
	</div>
</Shot>
