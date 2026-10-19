<script lang="ts">
	import Card from '@web/components/ui/Card.svelte';
	import Select from '@web/components/ui/Select.svelte';
	import type { SourceRef } from '../lib/settings.ts';
	import type { Panel } from './panel.svelte.ts';

	let { panel }: { panel: Panel } = $props();

	const options = $derived([
		...(panel.session?.profiles ?? []).map((p) => ({
			value: `profile:${p.id}`,
			label: `Profile: ${p.name}`
		})),
		...(panel.session?.documents ?? []).map((d) => ({
			value: `document:${d.id}`,
			label: `CV: ${d.name}`
		}))
	]);

	const value = $derived(panel.source ? `${panel.source.kind}:${panel.source.id}` : '');

	const why = $derived.by(() => {
		const job = panel.pageJob;
		if (panel.reason === 'job' && job) {
			return `The CV you tailored for ${job.title || 'this job'}${job.company ? ` at ${job.company}` : ''}.`;
		}
		if (panel.reason === 'default') return 'Your default profile.';
		return '';
	});

	function choose(event: Event) {
		const [kind, id] = (event.currentTarget as HTMLSelectElement).value.split(':');
		if ((kind === 'profile' || kind === 'document') && id) {
			void panel.chooseSource({ kind, id } satisfies SourceRef);
		}
	}
</script>

<Card>
	{#if options.length === 0}
		<div class="flex flex-col gap-1">
			<p class="text-base text-fg">You have no profiles yet.</p>
			<p class="text-sm text-fg-muted">
				Import your CV or enter your experience in Chameleon vitae first.
			</p>
		</div>
	{:else}
		<Select label="Fill from" {options} {value} onchange={choose} help={why || undefined} />
	{/if}
</Card>
