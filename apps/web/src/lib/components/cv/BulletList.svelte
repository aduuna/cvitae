<script lang="ts">
	import { tick } from 'svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import Textarea from '#lib/components/ui/Textarea.svelte';
	import { newBullet } from '#lib/cv/factory.ts';
	import type { Bullet } from '#lib/cv/types.ts';
	import SortableList from './SortableList.svelte';

	interface Props {
		bullets: Bullet[];
		/** Names the list for screen readers, for example "Bullets for Acme". */
		label: string;
		addLabel?: string;
	}

	let { bullets = $bindable(), label, addLabel = 'Add bullet' }: Props = $props();

	let list: HTMLDivElement | undefined = $state();

	async function add() {
		const bullet = newBullet();
		bullets.push(bullet);
		await tick();
		list?.querySelector<HTMLTextAreaElement>(`[data-bullet-id="${bullet.id}"]`)?.focus();
	}

	function remove(index: number) {
		bullets.splice(index, 1);
	}
</script>

<div bind:this={list} class="flex flex-col gap-2">
	{#if bullets.length > 0}
		<SortableList bind:items={bullets} noun="bullet" {label} gap="sm">
			{#snippet row(bullet, index)}
				<div class="flex items-start gap-1">
					<div class="min-w-0 flex-1">
						<Textarea
							bind:value={bullet.text}
							rows={2}
							aria-label="Bullet {index + 1}"
							data-bullet-id={bullet.id}
							placeholder="What you did and what changed because of it"
						/>
					</div>
					<IconButton
						label="Delete bullet {index + 1}"
						icon="delete"
						size="sm"
						onclick={() => remove(index)}
					/>
				</div>
			{/snippet}
		</SortableList>
	{/if}
	<div>
		<Button variant="ghost" size="sm" icon="new" onclick={add}>{addLabel}</Button>
	</div>
</div>
