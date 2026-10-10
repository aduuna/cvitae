<script lang="ts">
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import { newLink, objectKey } from '#lib/cv/factory.ts';
	import type { Basics, Link } from '#lib/cv/types.ts';
	import SortableList from './SortableList.svelte';

	let { basics = $bindable() }: { basics: Basics } = $props();
</script>

<Card title="Basics">
	<div class="@container flex flex-col gap-4">
		<div class="grid grid-cols-1 gap-3 @md:grid-cols-2">
			<Input label="Name" bind:value={basics.name} autocomplete="name" />
			<Input label="Headline" bind:value={basics.headline} placeholder="Senior data engineer" />
			<Input label="Email" type="email" bind:value={basics.email} autocomplete="email" />
			<Input label="Phone" type="tel" bind:value={basics.phone} autocomplete="tel" />
			<Input label="Location" bind:value={basics.location} placeholder="London, UK" />
		</div>

		<div class="flex flex-col gap-2">
			<p class="text-sm font-medium text-fg">Links</p>
			{#if basics.links.length > 0}
				<SortableList bind:items={basics.links} noun="link" label="Links" key={objectKey} gap="sm">
					{#snippet row(link: Link, index: number)}
						<div class="flex items-start gap-2">
							<div class="grid min-w-0 flex-1 grid-cols-1 gap-2 @md:grid-cols-[1fr_2fr]">
								<Input
									aria-label="Link {index + 1} label"
									placeholder="GitHub"
									bind:value={link.label}
								/>
								<Input
									aria-label="Link {index + 1} address"
									type="url"
									placeholder="https://github.com/you"
									bind:value={link.url}
								/>
							</div>
							<IconButton
								label="Delete link {index + 1}"
								icon="delete"
								size="sm"
								onclick={() => basics.links.splice(index, 1)}
							/>
						</div>
					{/snippet}
				</SortableList>
			{/if}
			<div>
				<Button variant="ghost" size="sm" icon="new" onclick={() => basics.links.push(newLink())}>
					Add link
				</Button>
			</div>
		</div>
	</div>
</Card>
