<script lang="ts">
	import { asset } from '$app/paths';
	import Badge from '#lib/components/ui/Badge.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import type { IconName } from '#lib/components/ui/icons.ts';
	import Placeholder from '#lib/components/ui/Placeholder.svelte';
	import MockButton from './MockButton.svelte';
	import MockSegmented from './MockSegmented.svelte';

	const rail: IconName[] = ['documents', 'profiles', 'tailor', 'templates', 'settings'];
</script>

{#snippet field(label: string, value: string)}
	<div class="flex flex-col gap-1.5">
		<span class="text-sm font-medium text-fg">{label}</span>
		<span
			class="flex h-8 items-center truncate rounded-md border border-line-strong bg-surface px-2.5 text-base text-fg"
		>
			{value}
		</span>
	</div>
{/snippet}

<!-- The CV editor as it looks in the app: icon rail, form, live preview. -->
<div
	role="img"
	aria-label="The CV editor: the CV's content in a form on the left, the rendered page on the right."
	class="pointer-events-none overflow-hidden rounded-lg border border-line bg-surface text-left shadow-pop select-none"
>
	<div class="flex h-12 items-center justify-between gap-4 border-b border-line px-4">
		<span class="truncate text-lg font-semibold text-fg">Lumen Payments, senior data engineer</span>
		<div class="flex shrink-0 items-center gap-2">
			<span class="hidden text-sm text-fg-muted sm:inline">Saved</span>
			<span class="hidden sm:inline-flex"><Badge variant="outline">1 page</Badge></span>
			<span
				class="hidden h-8 w-36 items-center justify-between rounded-md border border-line-strong bg-surface px-2.5 text-base text-fg md:flex"
			>
				Modern
				<Icon name="chevron-down" />
			</span>
			<MockButton variant="primary" icon="download" label="Export PDF" />
		</div>
	</div>

	<div class="flex h-100 sm:h-120">
		<div class="hidden w-14 shrink-0 flex-col items-center gap-1 border-r border-line py-2 lg:flex">
			{#each rail as name, index (name)}
				<span
					class={[
						'flex size-8 items-center justify-center rounded-md',
						index === 0 ? 'bg-muted text-fg' : 'text-fg-muted'
					]}
				>
					<Icon {name} />
				</span>
			{/each}
		</div>

		<div
			class="hidden w-72 shrink-0 flex-col gap-4 overflow-hidden border-r border-line bg-canvas p-4 md:flex lg:w-90"
		>
			<div class="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
				<span class="text-lg font-semibold text-fg">Basics</span>
				{@render field('Name', 'Ama Owusu-Mensah')}
				{@render field('Headline', 'Senior data engineer')}
			</div>
			<div class="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
				<span class="text-lg font-semibold text-fg">Experience</span>
				<div class="flex flex-col gap-0.5">
					<span class="text-base font-medium text-fg">Lead data engineer</span>
					<span class="text-sm text-fg-muted">Northwind Consulting, Mar 2021 to present</span>
				</div>
				<div class="flex gap-1.5 text-sm text-fg">
					<span class="mt-0.5 text-fg-faint"><Icon name="drag" /></span>
					<span
						class="flex-1 rounded-md border border-line-strong bg-surface px-2.5 py-1.5 leading-5"
					>
						Rebuilt <b>140</b> nightly batch pipelines in Spark on EMR, cutting runtime by
						<b>62%</b>.
					</span>
				</div>
				<div class="flex gap-1.5 text-sm text-fg">
					<span class="mt-0.5 text-fg-faint"><Icon name="drag" /></span>
					<span
						class="flex-1 rounded-md border border-line-strong bg-surface px-2.5 py-1.5 leading-5"
					>
						Built a streaming fraud-signal pipeline on Kafka that serves
						<Placeholder>number of analysts</Placeholder> analysts.
					</span>
				</div>
			</div>
		</div>

		<div class="flex min-w-0 flex-1 flex-col bg-canvas">
			<div
				class="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-line bg-surface px-3"
			>
				<span class="text-sm text-fg-muted tabular-nums">1 page</span>
				<MockSegmented options={['Fit', '75%', '100%']} selected="Fit" />
			</div>
			<div class="flex min-h-0 flex-1 justify-center overflow-hidden px-6 pt-6">
				<img
					src={asset('landing/modern.png')}
					alt=""
					width="595"
					height="842"
					class="h-auto w-full max-w-130 self-start bg-paper shadow-page"
					draggable="false"
				/>
			</div>
		</div>
	</div>
</div>
