<script lang="ts" module>
	export const dialogSizes = {
		sm: 'max-w-100',
		md: 'max-w-140'
	} as const;
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import { focusable, trapTab } from './focus';
	import IconButton from './IconButton.svelte';

	interface Props {
		open: boolean;
		title: string;
		size?: keyof typeof dialogSizes;
		/** Body content. */
		children: Snippet;
		/** Actions, right-aligned; put the primary action last. */
		footer?: Snippet;
		/** Called when the user dismisses the dialog (Escape, close button or backdrop). */
		onclose?: () => void;
	}

	let { open = $bindable(), title, size = 'sm', children, footer, onclose }: Props = $props();

	const id = $props.id();
	let panel: HTMLDivElement | undefined = $state();

	function close() {
		open = false;
		onclose?.();
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			event.preventDefault();
			event.stopPropagation();
			close();
		} else if (panel) {
			trapTab(event, panel);
		}
	}

	function onBackdropPointerDown(event: PointerEvent) {
		if (event.target === event.currentTarget) close();
	}

	// Move focus into the dialog on open and give it back to the opener on close.
	$effect(() => {
		if (!open || !panel) return;
		const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
		const first = focusable(panel).find((el) => !el.hasAttribute('data-dialog-close'));
		(first ?? panel).focus();
		return () => opener?.focus();
	});
</script>

{#if open}
	<div
		role="presentation"
		class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-fg/30 px-4 pt-[15vh] pb-4"
		onpointerdown={onBackdropPointerDown}
	>
		<div
			bind:this={panel}
			role="dialog"
			aria-modal="true"
			aria-labelledby="{id}-title"
			tabindex="-1"
			{onkeydown}
			class={[
				'w-full animate-pop-in rounded-lg border border-line bg-surface shadow-pop',
				dialogSizes[size]
			]}
		>
			<header class="flex items-center justify-between gap-4 px-5 pt-4 pb-2">
				<h2 id="{id}-title" class="text-lg font-semibold text-fg">{title}</h2>
				<IconButton label="Close" icon="close" size="sm" onclick={close} data-dialog-close="" />
			</header>
			<div class="px-5 py-2 text-base text-fg">
				{@render children()}
			</div>
			{#if footer}
				<footer class="flex justify-end gap-2 px-5 pt-4 pb-5">
					{@render footer()}
				</footer>
			{/if}
		</div>
	</div>
{/if}
