<script lang="ts">
	import RichText from '#lib/components/cv/RichText.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import type { BulletDiff, DroppedBullet, FactIssue } from '#lib/cv/types.ts';

	interface Props {
		changes: BulletDiff[];
		dropped: DroppedBullet[];
		issues: FactIssue[];
	}

	let { changes, dropped, issues }: Props = $props();

	/** Consecutive changes of the same entry, in CV order. */
	const groups = $derived(
		changes.reduce<{ entry: string; items: BulletDiff[] }[]>((all, change) => {
			const last = all.at(-1);
			if (last?.entry === change.entry) last.items.push(change);
			else all.push({ entry: change.entry, items: [change] });
			return all;
		}, [])
	);
</script>

<div class="flex flex-col gap-6">
	{#if issues.length > 0}
		<section aria-labelledby="corrected" class="rounded-lg border border-line bg-surface p-4">
			<h3 id="corrected" class="flex items-center gap-2 text-base font-semibold text-fg">
				<Icon name="placeholder-warning" />
				Corrected by the fact check ({issues.length})
			</h3>
			<ul class="mt-2 flex flex-col gap-1.5 text-sm text-fg">
				{#each issues as issue, index (index)}
					<li>{issue.message}</li>
				{/each}
			</ul>
		</section>
	{/if}

	{#each groups as group (group.entry + group.items[0]?.source_id)}
		<section>
			<h3 class="mb-2 text-sm font-medium text-fg-muted">{group.entry}</h3>
			<ul class="flex flex-col gap-3">
				{#each group.items as change (change.source_id)}
					<li class="rounded-lg border border-line bg-surface p-3">
						{#if change.text === change.source_text}
							<p class="text-base text-fg"><RichText text={change.text} /></p>
							<p class="mt-1 text-xs font-medium text-fg-muted">Kept as written</p>
						{:else}
							<p class="text-sm text-fg-muted"><RichText text={change.source_text} /></p>
							<p class="mt-1.5 text-base text-fg"><RichText text={change.text} /></p>
						{/if}
						{#if change.rationale}
							<p class="mt-1.5 text-xs text-fg-muted">{change.rationale}</p>
						{/if}
					</li>
				{/each}
			</ul>
		</section>
	{/each}

	{#if dropped.length > 0}
		<section>
			<h3 class="mb-2 text-sm font-medium text-fg-muted">Left out ({dropped.length})</h3>
			<ul class="flex flex-col gap-2 text-sm text-fg-muted">
				{#each dropped as bullet (bullet.source_id)}
					<li>
						<span class="text-fg">{bullet.entry}:</span>
						<RichText text={bullet.text} />
					</li>
				{/each}
			</ul>
		</section>
	{/if}
</div>
