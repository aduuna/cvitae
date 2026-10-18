<script lang="ts">
	import Badge from '#lib/components/ui/Badge.svelte';
	import Placeholder from '#lib/components/ui/Placeholder.svelte';
	import MockButton from './MockButton.svelte';
	import Shot from './Shot.svelte';
</script>

<Shot
	label="Tailoring: a pasted job description, then the review of each rewritten bullet under its source, with a highlighted placeholder where a number is missing."
>
	<div class="flex flex-col gap-3">
		<div class="rounded-lg border border-line bg-surface p-4">
			<span class="text-sm font-medium text-fg">Job description</span>
			<div
				class="mt-1.5 flex flex-col gap-1 rounded-md border border-line-strong bg-surface px-2.5 py-2 text-sm text-fg-muted"
			>
				<span class="font-medium text-fg">Senior Data Engineer, Payments Platform</span>
				<span>Lumen Payments, London, UK</span>
				<span class="mt-1 line-clamp-2">
					Design, build and run batch pipelines in Spark and streaming pipelines on Kafka. Own our
					dbt project and help analysts write models they can maintain themselves.
				</span>
			</div>
			<div class="mt-3 flex flex-wrap items-center justify-between gap-2">
				<span class="text-sm text-fg-muted">Data engineering profile, MiMo Flash</span>
				<MockButton variant="primary" icon="tailor" label="Tailor CV" />
			</div>
		</div>

		<div class="rounded-lg border border-line bg-surface p-4">
			<div class="flex gap-4 border-b border-line text-base">
				<span class="inline-flex h-9 items-center text-fg-muted">Preview</span>
				<span
					class="-mb-px inline-flex h-9 items-center border-b-2 border-accent font-medium text-fg"
				>
					Changes
				</span>
				<span class="inline-flex h-9 items-center text-fg-muted">Gaps</span>
			</div>
			<div class="mt-4 flex flex-col gap-4 text-sm">
				<div class="flex flex-col gap-1">
					<span class="text-fg-muted">
						Migrated <b>140</b> nightly batch jobs from on-premise Hadoop to Spark on EMR, cutting
						runtime by <b>62%</b>.
					</span>
					<span class="text-fg">
						Rebuilt <b>140</b> nightly batch pipelines in Spark on EMR, cutting runtime by
						<b>62%</b>.
					</span>
				</div>
				<div class="flex flex-col gap-1">
					<span class="text-fg-muted"
						>Built a streaming fraud-signal pipeline on Kafka for analysts.</span
					>
					<span class="text-fg">
						Built a streaming fraud-signal pipeline on Kafka that serves
						<Placeholder>number of analysts</Placeholder> analysts.
					</span>
				</div>
				<div class="flex flex-wrap items-center gap-2 border-t border-line pt-3 text-fg-muted">
					Not in your profile:
					<Badge variant="outline">Snowflake</Badge>
					<Badge variant="outline">Kubernetes</Badge>
				</div>
			</div>
		</div>
	</div>
</Shot>
