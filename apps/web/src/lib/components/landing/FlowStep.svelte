<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import type { IconName } from '#lib/components/ui/icons.ts';

	interface Props {
		step: number;
		icon: IconName;
		title: string;
		/** The explanation, one or more paragraphs. */
		children: Snippet;
		/** A picture of the step in the app. */
		shot: Snippet;
	}

	let { step, icon, title, children, shot }: Props = $props();
</script>

<li class="group relative pb-16 pl-12 last:pb-0 sm:pl-16">
	<!-- The thread that joins each step to the next. -->
	<span aria-hidden="true" class="absolute top-10 bottom-2 left-4 w-px bg-line group-last:hidden"
	></span>
	<span
		aria-hidden="true"
		class="absolute top-0 left-0 flex size-8 items-center justify-center rounded-full border border-line-strong bg-surface text-fg"
	>
		<Icon name={icon} />
	</span>
	<div class="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-12">
		<div class="flex flex-col gap-3 pt-1.5">
			<p class="font-mono text-sm text-fg-muted">Step {step}</p>
			<h3 class="text-xl font-semibold text-fg">{title}</h3>
			<div class="flex max-w-120 flex-col gap-3 text-lg text-fg-muted">{@render children()}</div>
		</div>
		{@render shot()}
	</div>
</li>
