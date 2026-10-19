<script lang="ts">
	import { onMount } from 'svelte';
	import Logo from '@web/components/shell/Logo.svelte';
	import Button from '@web/components/ui/Button.svelte';
	import Card from '@web/components/ui/Card.svelte';
	import EmptyState from '@web/components/ui/EmptyState.svelte';
	import Skeleton from '@web/components/ui/Skeleton.svelte';
	import Toast from '@web/components/ui/Toast.svelte';
	import { theme } from '@web/theme.svelte.ts';
	import DetailsCard from './DetailsCard.svelte';
	import FillCard from './FillCard.svelte';
	import JobCard from './JobCard.svelte';
	import { Panel } from './panel.svelte.ts';
	import SettingsCard from './SettingsCard.svelte';
	import SourceCard from './SourceCard.svelte';

	interface Props {
		panel?: Panel;
	}

	let { panel = new Panel() }: Props = $props();

	onMount(() => {
		void panel.start();
	});

	$effect(() => {
		document.documentElement.dataset.theme = theme.resolved;
	});
</script>

<div class="flex min-h-dvh flex-col gap-3 bg-canvas p-3 text-fg">
	<header class="flex items-center gap-2 px-1">
		<Logo />
		<h1 class="text-base font-semibold">Chameleon vitae</h1>
	</header>

	{#if panel.status === 'loading'}
		<Card><Skeleton lines={3} /></Card>
	{:else if panel.status === 'disconnected'}
		<Card>
			<EmptyState
				icon="extension"
				title="Connect your account"
				hint="Sign in to Chameleon vitae in a new tab and connect this browser. The extension then fills applications from your profiles and CVs."
				actionLabel="Connect"
				onaction={() => panel.connect()}
			/>
		</Card>
	{:else if panel.status === 'offline'}
		<Card>
			<div class="flex flex-col gap-3">
				<p class="text-base text-fg" role="alert">{panel.problem}</p>
				<div><Button onclick={() => panel.reload()}>Try again</Button></div>
			</div>
		</Card>
	{:else}
		<SourceCard {panel} />
		<FillCard {panel} />
		<JobCard {panel} />
		<DetailsCard {panel} />
		<SettingsCard {panel} />
	{/if}
</div>

<Toast />
