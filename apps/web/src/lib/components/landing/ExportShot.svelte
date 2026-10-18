<script lang="ts">
	import { asset } from '$app/paths';
	import Icon from '#lib/components/ui/Icon.svelte';
	import MockButton from './MockButton.svelte';
	import Shot from './Shot.svelte';
</script>

<Shot label="Exporting: a one-page PDF named after the person and the company, ready to download.">
	<div class="flex items-center gap-5 rounded-lg border border-line bg-surface p-4 sm:p-5">
		<img
			src={asset('landing/technical.png')}
			alt=""
			width="595"
			height="842"
			loading="lazy"
			draggable="false"
			class="h-auto w-24 shrink-0 rounded-sm bg-paper shadow-page sm:w-32"
		/>
		<div class="flex min-w-0 flex-1 flex-col items-start gap-3">
			<span class="flex max-w-full flex-col gap-1">
				<span class="truncate font-mono text-sm text-fg">
					Ama-Owusu-Mensah-CV-Lumen-Payments.pdf
				</span>
				<span class="text-sm text-fg-muted">1 page, A4</span>
			</span>
			<span class="flex items-center gap-1.5 text-sm text-fg-muted">
				<Icon name="check" />
				No placeholders left
			</span>
			<MockButton variant="primary" icon="download" label="Export PDF" />
		</div>
	</div>
</Shot>
