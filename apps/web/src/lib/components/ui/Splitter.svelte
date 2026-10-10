<script lang="ts">
	interface Props {
		/** Size in px of the panel before the splitter. */
		value: number;
		min: number;
		max: number;
		/** Pixels per arrow key press; Shift moves five steps. */
		step?: number;
		/** Accessible name, for example "Resize edit panel". */
		label: string;
		/** Called when a resize finishes (key press or pointer release), for persisting the size. */
		onchange?: (value: number) => void;
	}

	let { value = $bindable(), min, max, step = 16, label, onchange }: Props = $props();

	let dragging = $state(false);
	let startX = 0;
	let startValue = 0;

	function clamp(next: number): number {
		return Math.min(max, Math.max(min, Math.round(next)));
	}

	function onkeydown(event: KeyboardEvent) {
		const delta = event.shiftKey ? step * 5 : step;
		const targets: Record<string, number> = {
			ArrowLeft: value - delta,
			ArrowRight: value + delta,
			Home: min,
			End: max
		};
		const next = targets[event.key];
		if (next === undefined) return;
		event.preventDefault();
		value = clamp(next);
		onchange?.(value);
	}

	function onpointerdown(event: PointerEvent) {
		if (event.button !== 0) return;
		event.preventDefault();
		dragging = true;
		startX = event.clientX;
		startValue = value;
		(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
	}

	function onpointermove(event: PointerEvent) {
		if (dragging) value = clamp(startValue + event.clientX - startX);
	}

	function onpointerup() {
		if (!dragging) return;
		dragging = false;
		onchange?.(value);
	}
</script>

<!-- A focusable separator is an interactive widget in WAI-ARIA (window splitter pattern). -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<div
	role="separator"
	aria-orientation="vertical"
	aria-label={label}
	aria-valuenow={value}
	aria-valuemin={min}
	aria-valuemax={max}
	tabindex="0"
	{onkeydown}
	{onpointerdown}
	{onpointermove}
	{onpointerup}
	onpointercancel={onpointerup}
	class="group relative w-1 shrink-0 cursor-col-resize touch-none select-none"
>
	<span
		class={[
			'absolute inset-y-0 left-1/2 w-px -translate-x-1/2 transition-colors duration-120 ease-out',
			dragging ? 'bg-fg-muted' : 'bg-line-strong group-hover:bg-fg-muted'
		]}
	></span>
</div>
