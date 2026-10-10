<script lang="ts">
	import Card from '#lib/components/ui/Card.svelte';
	import Menu from '#lib/components/ui/Menu.svelte';
	import Textarea from '#lib/components/ui/Textarea.svelte';
	import { newSection, sectionKinds } from '#lib/cv/factory.ts';
	import type { CvContent } from '#lib/cv/types.ts';
	import BasicsEditor from './BasicsEditor.svelte';
	import SectionEditor from './SectionEditor.svelte';
	import SortableList from './SortableList.svelte';

	interface Props {
		content: CvContent;
		/** Read-only: every control is disabled (the editor on narrow screens). */
		disabled?: boolean;
	}

	let { content = $bindable(), disabled = false }: Props = $props();

	const addItems = sectionKinds.map(({ kind, title }) => ({
		label: title,
		onselect: () => content.sections.push(newSection(kind))
	}));
</script>

<!-- A disabled fieldset disables every control inside it. -->
<fieldset {disabled} class="flex min-w-0 flex-col gap-6">
	<legend class="sr-only">CV content</legend>
	<BasicsEditor bind:basics={content.basics} />

	<Card title="Summary">
		<Textarea
			aria-label="Summary"
			bind:value={content.summary}
			rows={4}
			data-field="summary"
			help="Use **bold** for key figures. Write [[what is missing]] for anything you still need to fill in."
		/>
	</Card>

	<div class="flex flex-col gap-3">
		<p class="text-sm text-fg-muted">
			Drag the handles, or press Alt+Up and Alt+Down, to reorder sections, entries and bullets.
		</p>
		<SortableList bind:items={content.sections} noun="section" label="Sections" {disabled}>
			{#snippet row(entry, index)}
				<SectionEditor
					bind:section={() => entry, (value) => (content.sections[index] = value)}
					ondelete={() => content.sections.splice(index, 1)}
				/>
			{/snippet}
		</SortableList>
		<div>
			<Menu text="Add section" icon="new" align="start" items={addItems} />
		</div>
	</div>
</fieldset>
