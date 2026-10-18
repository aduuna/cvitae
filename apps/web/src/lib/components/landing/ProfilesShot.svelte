<script lang="ts">
	import Badge from '#lib/components/ui/Badge.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import Shot from './Shot.svelte';

	const profiles = [
		{ name: 'Data engineering', edited: 'Edited today', isDefault: true },
		{ name: 'Backend', edited: 'Edited 3 days ago', isDefault: false },
		{ name: 'Analytics engineering', edited: 'Edited last month', isDefault: false }
	];
</script>

<Shot label="Profiles: three career profiles side by side, one marked as the default.">
	<ul class="grid grid-cols-2 gap-3">
		{#each profiles as profile (profile.name)}
			<li class="flex min-h-32 flex-col gap-3 rounded-lg border border-line bg-surface p-4">
				<span class="flex items-center gap-2">
					<span class="flex size-9 items-center justify-center rounded-md bg-muted text-fg-muted">
						<Icon name="profiles" />
					</span>
					{#if profile.isDefault}<Badge>Default</Badge>{/if}
				</span>
				<span class="text-base font-semibold text-fg">{profile.name}</span>
				<span class="mt-auto text-sm text-fg-muted">{profile.edited}</span>
			</li>
		{/each}
		<li
			class="flex min-h-32 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line-strong text-sm text-fg-muted"
		>
			<Icon name="new" />
			New profile
		</li>
	</ul>
</Shot>
