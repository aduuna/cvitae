<script lang="ts">
	import { onDestroy } from 'svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';

	interface Props {
		/** What is happening, in order; the text moves on every `stepSeconds`. */
		steps: string[];
		stepSeconds?: number;
		/** For example "Generated with Claude". */
		caption?: string;
		oncancel: () => void;
	}

	let { steps, stepSeconds = 8, caption, oncancel }: Props = $props();

	let elapsed = $state(0);
	const started = Date.now();
	const timer = setInterval(() => {
		elapsed = Math.floor((Date.now() - started) / 1000);
	}, 1000);
	onDestroy(() => clearInterval(timer));

	const step = $derived(steps[Math.min(Math.floor(elapsed / stepSeconds), steps.length - 1)]);
</script>

<Card>
	<div class="flex flex-col gap-4">
		<div class="flex items-center justify-between gap-4">
			<p class="text-base font-medium text-fg" aria-live="polite">{step}</p>
			<span class="font-mono text-sm text-fg-muted tabular-nums" aria-label="{elapsed} seconds">
				{elapsed}s
			</span>
		</div>
		<div
			class="h-1 overflow-hidden rounded-sm bg-muted"
			role="progressbar"
			aria-label="Working"
			aria-busy="true"
		>
			<div class="h-full w-2/5 animate-indeterminate rounded-sm bg-accent"></div>
		</div>
		<div class="flex items-center justify-between gap-4">
			<p class="text-sm text-fg-muted">
				{caption ? `${caption}. ` : ''}This can take 1 to 2 minutes.
			</p>
			<Button variant="ghost" size="sm" onclick={oncancel}>Cancel</Button>
		</div>
	</div>
</Card>
