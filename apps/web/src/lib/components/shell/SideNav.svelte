<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { MediaQuery } from 'svelte/reactivity';
	import Icon from '#lib/components/ui/Icon.svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import Tooltip from '#lib/components/ui/Tooltip.svelte';
	import { isActive, navItems } from './nav';
	import { loadCollapsed, saveCollapsed } from './sidenav-state';

	// Under 1024px the nav is always the icon rail (docs/DESIGN.md, Breakpoints).
	const wide = new MediaQuery('min-width: 1024px', true);

	let userCollapsed = $state(loadCollapsed());
	const collapsed = $derived(userCollapsed || !wide.current);

	function toggle() {
		userCollapsed = !userCollapsed;
		saveCollapsed(userCollapsed);
	}
</script>

<nav
	aria-label="Main"
	data-collapsed={collapsed}
	class={[
		'flex h-full shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-180 ease-out',
		collapsed ? 'w-14' : 'w-60'
	]}
>
	<div
		class={[
			'flex h-12 shrink-0 items-center border-b border-line',
			collapsed ? 'justify-center' : 'justify-between pr-2 pl-4'
		]}
	>
		{#if !collapsed}
			<span class="text-base font-semibold text-fg">Chameleon vitae</span>
		{/if}
		{#if wide.current}
			<IconButton
				label={collapsed ? 'Expand side nav' : 'Collapse side nav'}
				icon={collapsed ? 'nav-expand' : 'nav-collapse'}
				tooltipSide={collapsed ? 'right' : 'bottom'}
				aria-expanded={!collapsed}
				onclick={toggle}
			/>
		{:else}
			<span class="text-base font-semibold text-fg" aria-hidden="true">CV</span>
		{/if}
	</div>

	<ul class="flex flex-col gap-0.5 p-2">
		{#each navItems as item (item.href)}
			{@const active = isActive(item, page.url.pathname)}
			<li>
				<Tooltip text={item.label} side="right" describe={false} disabled={!collapsed}>
					{#snippet children(trigger)}
						<a
							{...trigger}
							href={resolve(item.href)}
							aria-current={active ? 'page' : undefined}
							class={[
								'relative flex h-8 items-center gap-2 rounded-md px-2 text-base transition-colors duration-120 ease-out',
								collapsed && 'justify-center',
								active
									? 'bg-muted font-medium text-fg'
									: 'text-fg-muted hover:bg-subtle hover:text-fg'
							]}
						>
							{#if active}
								<span
									aria-hidden="true"
									class="absolute inset-y-1.5 -left-2 w-0.5 rounded-r-sm bg-accent"
								></span>
							{/if}
							<Icon name={item.icon} />
							<span class={collapsed ? 'sr-only' : 'truncate'}>{item.label}</span>
						</a>
					{/snippet}
				</Tooltip>
			</li>
		{/each}
	</ul>
</nav>
