<script lang="ts" module>
	import type { IconName } from './icons';

	export interface MenuItem {
		label: string;
		icon?: IconName;
		/** Shown right-aligned, for example "Ctrl+D". */
		shortcut?: string;
		danger?: boolean;
		disabled?: boolean;
		onselect: () => void;
	}
</script>

<script lang="ts">
	import { tick } from 'svelte';
	import Button from './Button.svelte';
	import Icon from './Icon.svelte';
	import IconButton from './IconButton.svelte';
	import { nextIndex } from './roving';

	type Props = {
		items: MenuItem[];
		/** Trigger icon: defaults to "more" for icon triggers, none for text triggers. */
		icon?: IconName;
		align?: 'start' | 'end';
		/** Open below the trigger (default) or above it, for triggers near the bottom edge. */
		placement?: 'bottom' | 'top';
	} & (
		| {
				/** Accessible name and tooltip of the icon trigger, e.g. "Actions for Backend CV". */
				label: string;
				text?: undefined;
		  }
		| {
				/** Visible trigger text, for example "Add section". */
				text: string;
				label?: undefined;
		  }
	);

	let { items, label, text, icon, align = 'end', placement = 'bottom' }: Props = $props();

	const id = $props.id();
	let open = $state(false);
	let root: HTMLDivElement | undefined = $state();
	let trigger: HTMLButtonElement | undefined = $state();
	let menu: HTMLDivElement | undefined = $state();

	function enabledItems(): HTMLButtonElement[] {
		return menu
			? Array.from(menu.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])'))
			: [];
	}

	async function show(focus: 'first' | 'last') {
		open = true;
		await tick();
		const elements = enabledItems();
		(focus === 'first' ? elements[0] : elements.at(-1))?.focus();
	}

	function hide(returnFocus: boolean) {
		open = false;
		if (returnFocus) trigger?.focus();
	}

	function onTriggerKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			show('first');
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			show('last');
		}
	}

	function onMenuKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			event.preventDefault();
			hide(true);
			return;
		}
		if (event.key === 'Tab') {
			hide(false);
			return;
		}
		if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') return;
		const elements = enabledItems();
		const current = elements.indexOf(document.activeElement as HTMLButtonElement);
		const next = nextIndex(event.key, Math.max(current, 0), elements.length);
		if (next === null) return;
		event.preventDefault();
		elements[next]?.focus();
	}

	function choose(item: MenuItem) {
		hide(true);
		item.onselect();
	}

	function onWindowPointerDown(event: PointerEvent) {
		if (open && root && !root.contains(event.target as Node)) hide(false);
	}
</script>

<svelte:window onpointerdown={onWindowPointerDown} />

<div bind:this={root} class="relative inline-flex">
	{#if text !== undefined}
		<Button
			bind:ref={trigger}
			id="{id}-trigger"
			{icon}
			aria-haspopup="menu"
			aria-expanded={open}
			aria-controls={open ? `${id}-menu` : undefined}
			onclick={() => (open ? hide(false) : show('first'))}
			onkeydown={onTriggerKeydown}
		>
			{text}
		</Button>
	{:else}
		<IconButton
			bind:ref={trigger}
			id="{id}-trigger"
			label={label ?? ''}
			icon={icon ?? 'more'}
			aria-haspopup="menu"
			aria-expanded={open}
			aria-controls={open ? `${id}-menu` : undefined}
			onclick={() => (open ? hide(false) : show('first'))}
			onkeydown={onTriggerKeydown}
		/>
	{/if}
	{#if open}
		<div
			bind:this={menu}
			id="{id}-menu"
			role="menu"
			aria-labelledby="{id}-trigger"
			tabindex="-1"
			onkeydown={onMenuKeydown}
			class={[
				'absolute z-40 flex min-w-48 animate-pop-in flex-col rounded-md border border-line bg-surface p-1 shadow-pop',
				placement === 'top' ? 'bottom-full mb-1' : 'top-full mt-1',
				align === 'end' ? 'right-0' : 'left-0'
			]}
		>
			{#each items as item (item.label)}
				<button
					type="button"
					role="menuitem"
					tabindex="-1"
					disabled={item.disabled}
					onclick={() => choose(item)}
					class={[
						'flex h-8 w-full items-center gap-2 rounded-sm px-2 text-left text-base whitespace-nowrap focus-visible:-outline-offset-2 enabled:hover:bg-subtle disabled:cursor-not-allowed disabled:opacity-40',
						item.danger ? 'text-danger' : 'text-fg'
					]}
				>
					{#if item.icon}
						<Icon name={item.icon} />
					{/if}
					<span class="flex-1">{item.label}</span>
					{#if item.shortcut}
						<span class="pl-4 text-xs text-fg-muted">{item.shortcut}</span>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>
