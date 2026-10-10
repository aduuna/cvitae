<script lang="ts" module>
	const tooltipClass =
		'pointer-events-none fixed z-50 rounded-sm bg-fg px-2 py-1 text-xs font-medium whitespace-nowrap text-surface';

	export interface TooltipTriggerProps {
		'aria-describedby'?: string;
		onpointerenter: (event: PointerEvent) => void;
		onpointerleave: () => void;
		onfocus: (event: FocusEvent) => void;
		onblur: () => void;
	}
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		text: string;
		side?: 'top' | 'right' | 'bottom';
		/** Link the tooltip with aria-describedby. Off when the trigger's label already says the same. */
		describe?: boolean;
		disabled?: boolean;
		/** Render the trigger element, spreading these props onto it. */
		children: Snippet<[TooltipTriggerProps]>;
	}

	let { text, side = 'top', describe = true, disabled = false, children }: Props = $props();

	const DELAY_MS = 400;
	const GAP_PX = 8;
	const id = $props.id();

	let visible = $state(false);
	let position = $state('');
	let timer: ReturnType<typeof setTimeout> | undefined;

	const placement = {
		top: (r: DOMRect) =>
			`left: ${r.left + r.width / 2}px; top: ${r.top - GAP_PX}px; transform: translate(-50%, -100%)`,
		right: (r: DOMRect) =>
			`left: ${r.right + GAP_PX}px; top: ${r.top + r.height / 2}px; transform: translateY(-50%)`,
		bottom: (r: DOMRect) =>
			`left: ${r.left + r.width / 2}px; top: ${r.bottom + GAP_PX}px; transform: translateX(-50%)`
	};

	function show(target: EventTarget | null) {
		if (disabled || !(target instanceof Element)) return;
		clearTimeout(timer);
		timer = setTimeout(() => {
			position = placement[side](target.getBoundingClientRect());
			visible = true;
		}, DELAY_MS);
	}

	function hide() {
		clearTimeout(timer);
		visible = false;
	}

	$effect(() => () => clearTimeout(timer));

	const trigger: TooltipTriggerProps = {
		get 'aria-describedby'() {
			return describe && !disabled ? id : undefined;
		},
		onpointerenter: (event) => show(event.currentTarget),
		onpointerleave: hide,
		onfocus: (event) => show(event.currentTarget),
		onblur: hide
	};

	function onWindowKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') hide();
	}
</script>

<svelte:window onkeydown={visible ? onWindowKeydown : undefined} />

{@render children(trigger)}
{#if describe && !disabled}
	<span
		{id}
		role="tooltip"
		data-state={visible ? 'open' : 'closed'}
		class={visible ? tooltipClass : 'sr-only'}
		style={visible ? position : ''}
	>
		{text}
	</span>
{:else if visible}
	<span aria-hidden="true" data-state="open" class={tooltipClass} style={position}>{text}</span>
{/if}
