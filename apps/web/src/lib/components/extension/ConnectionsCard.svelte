<script lang="ts">
	import { api, errorMessage, unwrap, type Schemas } from '#lib/api/client.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import { formatRelative } from '#lib/format.ts';

	type Connection = Schemas['ExtensionConnectionInfo'];

	interface Props {
		/** Null while loading. */
		connections: Connection[] | null;
	}

	let { connections = $bindable() }: Props = $props();
	let removing = $state<string | null>(null);

	async function disconnect(connection: Connection) {
		removing = connection.id;
		try {
			await unwrap(
				api.DELETE('/api/v1/extension/connections/{connection_id}', {
					params: { path: { connection_id: connection.id } }
				})
			);
			connections = (connections ?? []).filter((row) => row.id !== connection.id);
			toast.info(`${connection.label} is disconnected.`);
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			removing = null;
		}
	}

	function used(connection: Connection): string {
		const connected = `Connected ${formatRelative(connection.created_at)}`;
		return connection.last_used_at
			? `${connected}, last used ${formatRelative(connection.last_used_at)}`
			: `${connected}, not used yet`;
	}
</script>

<Card title="Connected browsers">
	{#if connections === null}
		<Skeleton lines={2} />
	{:else if connections.length === 0}
		<p class="text-base text-fg">No browser is connected.</p>
	{:else}
		<ul class="flex flex-col">
			{#each connections as connection (connection.id)}
				<li class="flex items-center gap-3 border-t border-line py-3 first:border-t-0 first:pt-0">
					<div class="min-w-0 flex-1">
						<p class="truncate text-base text-fg">{connection.label}</p>
						<p class="text-sm text-fg-muted">{used(connection)}</p>
					</div>
					<Button
						size="sm"
						variant="danger"
						loading={removing === connection.id}
						disabled={removing !== null}
						onclick={() => disconnect(connection)}
					>
						Disconnect
					</Button>
				</li>
			{/each}
		</ul>
	{/if}
</Card>
