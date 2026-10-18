<script lang="ts">
	import { asset } from '$app/paths';
	import { landingTemplates } from './templates';
	import MockSegmented from './MockSegmented.svelte';
	import Shot from './Shot.svelte';

	const selected = 'technical';

	// Lines from templates/technical/main.typ, shortened to fit.
	const source = [
		'#import "/_lib/cv.typ": *',
		'#let cv = json("data.json")',
		'',
		'#set page(margin: (x: 1.5cm, y: 1.3cm))',
		'#set text(font: "Geist", size: 9.5pt, hyphenate: false)'
	];
</script>

<Shot label="Editing: the five templates with Technical selected, and the same CV as Typst source.">
	<div class="flex flex-col gap-3">
		<div class="rounded-lg border border-line bg-surface p-4">
			<span class="text-sm font-medium text-fg">Template</span>
			<ul class="mt-3 grid grid-cols-5 gap-2 sm:gap-3">
				{#each landingTemplates as template (template.id)}
					{@const active = template.id === selected}
					<li class="flex min-w-0 flex-col items-center gap-1.5">
						<img
							src={asset(`landing/${template.id}.png`)}
							alt=""
							width="595"
							height="842"
							loading="lazy"
							draggable="false"
							class={[
								'h-auto w-full rounded-sm bg-paper shadow-page',
								active && 'outline-2 outline-offset-2 outline-accent'
							]}
						/>
						<span class={['truncate text-xs', active ? 'font-medium text-fg' : 'text-fg-muted']}>
							{template.name}
						</span>
					</li>
				{/each}
			</ul>
		</div>

		<div class="overflow-hidden rounded-lg border border-line bg-surface">
			<div class="flex items-center justify-between gap-3 border-b border-line px-3 py-2">
				<MockSegmented options={['Form', 'Typst']} selected="Typst" />
				<span class="font-mono text-sm text-fg-muted">main.typ</span>
			</div>
			<pre class="overflow-hidden px-4 py-3 font-mono text-sm text-fg"><code
					>{#each source as line, index (index)}<span class="block truncate"
							><span class="mr-4 inline-block w-4 text-right text-fg-faint select-none"
								>{index + 1}</span
							>{line}</span
						>{/each}</code
				></pre>
		</div>
	</div>
</Shot>
