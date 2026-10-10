<script lang="ts" module>
	import { formatBytes } from '#lib/format.ts';

	const ACCEPTED_TYPES: Record<string, string> = {
		pdf: 'application/pdf',
		docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
	};

	export const ACCEPT_ATTRIBUTE = [
		...Object.keys(ACCEPTED_TYPES).map((ext) => `.${ext}`),
		...Object.values(ACCEPTED_TYPES)
	].join(',');

	/** 10 MB, the import limit (docs/PRODUCT.md, Import). */
	export const DEFAULT_MAX_BYTES = 10 * 1024 * 1024;

	/** Returns a message for the user when the file cannot be used, else null. */
	export function validateUpload(file: File, maxBytes: number): string | null {
		const extension = file.name.includes('.') ? file.name.split('.').pop()!.toLowerCase() : '';
		const typeOk = extension in ACCEPTED_TYPES || Object.values(ACCEPTED_TYPES).includes(file.type);
		if (!typeOk) return 'This file type is not supported. Choose a PDF or DOCX file.';
		if (file.size > maxBytes) {
			return `This file is larger than ${formatBytes(maxBytes)}. Choose a smaller file.`;
		}
		return null;
	}
</script>

<script lang="ts">
	import Button from './Button.svelte';
	import Icon from './Icon.svelte';
	import IconButton from './IconButton.svelte';

	interface Props {
		file: File | null;
		/** Accessible name of the drop area. */
		label?: string;
		maxBytes?: number;
		disabled?: boolean;
		onfile?: (file: File | null) => void;
	}

	let {
		file = $bindable(null),
		label = 'CV file',
		maxBytes = DEFAULT_MAX_BYTES,
		disabled = false,
		onfile
	}: Props = $props();

	const id = $props.id();
	let input: HTMLInputElement | undefined = $state();
	let over = $state(false);
	let error = $state('');

	function take(candidate: File | undefined) {
		if (!candidate || disabled) return;
		const problem = validateUpload(candidate, maxBytes);
		if (problem) {
			error = problem;
			return;
		}
		error = '';
		file = candidate;
		onfile?.(candidate);
	}

	function remove() {
		file = null;
		error = '';
		onfile?.(null);
	}

	function ondragover(event: DragEvent) {
		event.preventDefault();
		if (!disabled) over = true;
	}

	function ondrop(event: DragEvent) {
		event.preventDefault();
		over = false;
		take(event.dataTransfer?.files[0]);
	}

	function onchange() {
		take(input?.files?.[0]);
		if (input) input.value = '';
	}
</script>

<div class="flex flex-col gap-1.5">
	<div
		role="group"
		aria-label={label}
		aria-describedby={error ? `${id}-error` : undefined}
		data-over={over || undefined}
		{ondragover}
		ondragleave={() => (over = false)}
		{ondrop}
		class={[
			'flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-8 text-center transition-colors duration-120 ease-out',
			over ? 'border-fg-muted bg-subtle' : 'bg-surface',
			!over && (error ? 'border-danger' : 'border-line-strong'),
			disabled && 'opacity-40'
		]}
	>
		{#if file}
			<div class="flex max-w-full items-center gap-2">
				<span class="text-fg-muted"><Icon name="file" /></span>
				<span class="truncate text-base text-fg">{file.name}</span>
				<span class="font-mono text-sm text-fg-muted">{formatBytes(file.size)}</span>
				<IconButton label="Remove file" icon="close" size="sm" {disabled} onclick={remove} />
			</div>
		{:else}
			<span class="text-fg-muted"><Icon name="import" /></span>
			<p class="text-base text-fg">Drop a PDF or DOCX file here</p>
			<p class="text-sm text-fg-muted">Up to {formatBytes(maxBytes)}</p>
			<div class="mt-2">
				<Button size="sm" {disabled} onclick={() => input?.click()}>Choose file</Button>
			</div>
		{/if}
		<input
			bind:this={input}
			type="file"
			accept={ACCEPT_ATTRIBUTE}
			hidden
			{disabled}
			data-testid="dropzone-input"
			{onchange}
		/>
	</div>
	{#if error}
		<p id="{id}-error" role="alert" class="text-sm text-danger">{error}</p>
	{/if}
</div>
