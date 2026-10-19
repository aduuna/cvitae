<script lang="ts">
	import Button from '@web/components/ui/Button.svelte';
	import Card from '@web/components/ui/Card.svelte';
	import Checkbox from '@web/components/ui/Checkbox.svelte';
	import type { Panel } from './panel.svelte.ts';

	let { panel }: { panel: Panel } = $props();

	let disconnecting = $state(false);

	async function disconnect() {
		disconnecting = true;
		await panel.disconnect();
		disconnecting = false;
	}
</script>

<Card title="Settings">
	<div class="flex flex-col gap-4">
		<Checkbox
			label="Offer to fill on job sites"
			help="When a job site shows an application form, a small offer appears in its corner. Nothing is read from your profile until you choose to fill."
			checked={panel.settings.offer}
			onchange={(event) => panel.setOffer((event.currentTarget as HTMLInputElement).checked)}
		/>
		<div class="flex flex-col gap-2 border-t border-line pt-3">
			<p class="text-sm text-fg-muted">
				Connected to <span class="text-fg">{panel.session?.email ?? panel.settings.email}</span>.
			</p>
			<div class="flex flex-wrap gap-2">
				<Button size="sm" onclick={() => panel.openApp('/app/profiles')}>Edit profiles</Button>
				<Button size="sm" variant="danger" loading={disconnecting} onclick={disconnect}>
					Disconnect
				</Button>
			</div>
		</div>
		<div>
			<Button size="sm" variant="ghost" onclick={() => panel.openApp('/privacy')}>
				Privacy policy
			</Button>
		</div>
	</div>
</Card>
