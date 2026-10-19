<script lang="ts">
	import Button from '@web/components/ui/Button.svelte';
	import Card from '@web/components/ui/Card.svelte';
	import IconButton from '@web/components/ui/IconButton.svelte';
	import { toast } from '@web/components/ui/toasts.svelte.ts';
	import { detailGroups } from './details.ts';
	import type { Panel } from './panel.svelte.ts';

	let { panel }: { panel: Panel } = $props();

	let open = $state(false);
	let loading = $state(false);
	let error = $state<string | null>(null);
	const groups = $derived(panel.details ? detailGroups(panel.details) : []);

	async function show() {
		if (!panel.details) {
			loading = true;
			error = await panel.loadDetails();
			loading = false;
		}
		open = error === null;
	}

	async function copy(label: string, value: string) {
		try {
			await navigator.clipboard.writeText(value);
			toast.info(`${label} copied.`);
		} catch {
			toast.error('The browser did not allow copying. Select the text and copy it instead.');
		}
	}
</script>

<Card title="Copy your details">
	{#if !open}
		<div class="flex flex-col gap-3">
			<p class="text-sm text-fg-muted">
				Some fields can't be filled for you, such as lists a site builds itself. Copy what they ask
				for from your {panel.sourceLabel || 'profile'}.
			</p>
			{#if error}
				<p class="text-sm text-danger" role="alert">{error}</p>
			{/if}
			<div><Button {loading} onclick={show}>Show details</Button></div>
		</div>
	{:else}
		<div class="flex flex-col gap-4">
			{#each groups as group, index (index)}
				<section class="flex flex-col gap-1">
					<h2 class="text-sm font-medium text-fg-muted">{group.title}</h2>
					<ul class="flex flex-col">
						{#each group.items as item, n (n)}
							<li class="flex items-start gap-2 py-1">
								<div class="min-w-0 flex-1">
									<p class="text-xs font-medium text-fg-muted">{item.label}</p>
									<p class="line-clamp-3 text-sm whitespace-pre-line text-fg">{item.value}</p>
								</div>
								<IconButton
									size="sm"
									icon="duplicate"
									label="Copy {item.label.toLowerCase()}"
									onclick={() => copy(item.label, item.value)}
								/>
							</li>
						{/each}
					</ul>
				</section>
			{/each}
			<div>
				<Button variant="ghost" size="sm" onclick={() => (open = false)}>Hide details</Button>
			</div>
		</div>
	{/if}
</Card>
