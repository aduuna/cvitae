<script lang="ts">
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import { api, errorMessage, unwrap, type Schemas } from '#lib/api/client.ts';
	import ConnectCard from '#lib/components/extension/ConnectCard.svelte';
	import ConnectionsCard from '#lib/components/extension/ConnectionsCard.svelte';
	import Page from '#lib/components/shell/Page.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import LinkButton from '#lib/components/ui/LinkButton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import { EXTENSION_STORES } from '#lib/extension/stores.ts';

	// The extension opens this page after it is installed, to be connected (CONNECT_PATH).
	let connections = $state<Schemas['ExtensionConnectionInfo'][] | null>(null);

	const published = EXTENSION_STORES.filter(
		(store): store is { browser: string; url: string } => store.url !== null
	);

	async function load() {
		try {
			connections = await unwrap(api.GET('/api/v1/extension/connections'));
		} catch (error) {
			connections ??= [];
			toast.error(errorMessage(error));
		}
	}

	onMount(load);
</script>

<Page title="Browser extension">
	<Card title="Fill applications from your profile">
		<div class="flex flex-col gap-4">
			<ul class="flex list-disc flex-col gap-1 pl-5 text-base text-fg">
				<li>Fills job application forms from a profile or CV, after you check what goes where.</li>
				<li>Attaches the CV you tailored for the job, as a PDF.</li>
				<li>Saves the job ad you are reading, so you can tailor a CV for it.</li>
			</ul>
			<p class="text-sm text-fg-muted">
				It reads your profiles and CVs only when you choose to fill a form, never changes or deletes
				them, and never submits an application. Check every field before you send it. <a
					href={resolve('/privacy')}
					class="text-fg underline underline-offset-4">How it handles your data</a
				>.
			</p>
			{#if published.length}
				<div class="flex flex-wrap gap-2">
					{#each published as store (store.browser)}
						<LinkButton href={store.url} target="_blank" rel="noopener" icon="extension">
							Get it for {store.browser}
						</LinkButton>
					{/each}
				</div>
			{:else}
				<p class="text-sm text-fg">
					The extension for Chrome and Firefox is not in the browser stores yet.
				</p>
			{/if}
		</div>
	</Card>

	<ConnectCard onconnected={load} />

	<ConnectionsCard bind:connections />
</Page>
