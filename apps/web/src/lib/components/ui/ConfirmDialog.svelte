<script lang="ts">
	import Button from './Button.svelte';
	import Dialog from './Dialog.svelte';
	import Input from './Input.svelte';

	interface Props {
		open: boolean;
		title: string;
		message: string;
		/** A verb for what happens, for example "Delete CV". */
		confirmLabel: string;
		cancelLabel?: string;
		/** Destructive action: the confirm button uses the danger variant. */
		danger?: boolean;
		/** When set, the user must type this text before confirming (account deletion). */
		confirmText?: string;
		/** Match what is typed without regard to case, as an email address is matched. */
		ignoreCase?: boolean;
		/**
		 * Gets what the user typed (trimmed; empty without `confirmText`). May return a promise; the
		 * button shows a spinner until it settles.
		 */
		onconfirm: (typed: string) => void | Promise<void>;
		oncancel?: () => void;
	}

	let {
		open = $bindable(),
		title,
		message,
		confirmLabel,
		cancelLabel = 'Cancel',
		danger = false,
		confirmText,
		ignoreCase = false,
		onconfirm,
		oncancel
	}: Props = $props();

	let typed = $state('');
	let busy = $state(false);

	const confirmed = $derived(
		confirmText === undefined ||
			(ignoreCase
				? typed.trim().toLowerCase() === confirmText.toLowerCase()
				: typed.trim() === confirmText)
	);

	$effect(() => {
		if (open) typed = '';
	});

	function cancel() {
		open = false;
		oncancel?.();
	}

	async function confirm() {
		if (!confirmed) return;
		busy = true;
		try {
			await onconfirm(typed.trim());
			open = false;
		} finally {
			busy = false;
		}
	}
</script>

<Dialog bind:open {title} size="sm" onclose={oncancel}>
	<p>{message}</p>
	{#if confirmText !== undefined}
		<form
			class="mt-4"
			onsubmit={(event) => {
				event.preventDefault();
				confirm();
			}}
		>
			<Input
				label="Type {confirmText} to confirm"
				bind:value={typed}
				autocomplete="off"
				spellcheck={false}
			/>
		</form>
	{/if}
	{#snippet footer()}
		<Button variant="secondary" onclick={cancel}>{cancelLabel}</Button>
		<Button
			variant={danger ? 'danger' : 'primary'}
			loading={busy}
			disabled={!confirmed}
			onclick={confirm}
		>
			{confirmLabel}
		</Button>
	{/snippet}
</Dialog>
