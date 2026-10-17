<script lang="ts">
	import Badge from '#lib/components/ui/Badge.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import {
		newCertification,
		newEducation,
		newExperience,
		newProject,
		newSkillGroup,
		sectionKinds
	} from '#lib/cv/factory.ts';
	import type { Section } from '#lib/cv/types.ts';
	import BulletList from './BulletList.svelte';
	import CertificationEditor from './CertificationEditor.svelte';
	import EducationEditor from './EducationEditor.svelte';
	import ExperienceEditor from './ExperienceEditor.svelte';
	import ProjectEditor from './ProjectEditor.svelte';
	import SkillGroupEditor from './SkillGroupEditor.svelte';
	import SortableList from './SortableList.svelte';

	interface Props {
		section: Section;
		ondelete: () => void;
	}

	let { section = $bindable(), ondelete }: Props = $props();

	let confirming = $state(false);

	const kindLabel = $derived(
		section.kind === 'custom'
			? 'Custom'
			: (sectionKinds.find((entry) => entry.kind === section.kind)?.title ?? section.kind)
	);
	const count = $derived(section[section.kind].length);
	const name = $derived(section.title.trim() || kindLabel);

	function requestDelete() {
		if (count > 0) confirming = true;
		else ondelete();
	}
</script>

<section
	aria-label={name}
	data-cv-id={section.id}
	class="@container rounded-lg border border-line bg-surface"
>
	<header class="flex items-center gap-2 border-b border-line py-3 pr-3 pl-4">
		<div class="min-w-0 flex-1">
			<Input aria-label="Section title" bind:value={section.title} />
		</div>
		<Badge variant="outline">{kindLabel}</Badge>
		<IconButton label="Delete section {name}" icon="delete" onclick={requestDelete} />
	</header>

	<div class="flex flex-col gap-3 p-4">
		{#if section.kind === 'experience'}
			<SortableList bind:items={section.experience} noun="role" label="Roles in {name}">
				{#snippet row(entry, index)}
					<ExperienceEditor
						bind:item={() => entry, (value) => (section.experience[index] = value)}
						ondelete={() => section.experience.splice(index, 1)}
					/>
				{/snippet}
			</SortableList>
			<div>
				<Button size="sm" icon="new" onclick={() => section.experience.push(newExperience())}>
					Add role
				</Button>
			</div>
		{:else if section.kind === 'projects'}
			<SortableList bind:items={section.projects} noun="project" label="Projects in {name}">
				{#snippet row(entry, index)}
					<ProjectEditor
						bind:item={() => entry, (value) => (section.projects[index] = value)}
						ondelete={() => section.projects.splice(index, 1)}
					/>
				{/snippet}
			</SortableList>
			<div>
				<Button size="sm" icon="new" onclick={() => section.projects.push(newProject())}>
					Add project
				</Button>
			</div>
		{:else if section.kind === 'education'}
			<SortableList
				bind:items={section.education}
				noun="education entry"
				label="Education in {name}"
			>
				{#snippet row(entry, index)}
					<EducationEditor
						bind:item={() => entry, (value) => (section.education[index] = value)}
						ondelete={() => section.education.splice(index, 1)}
					/>
				{/snippet}
			</SortableList>
			<div>
				<Button size="sm" icon="new" onclick={() => section.education.push(newEducation())}>
					Add education
				</Button>
			</div>
		{:else if section.kind === 'skills'}
			<SortableList bind:items={section.skills} noun="skill group" label="Skill groups in {name}">
				{#snippet row(entry, index)}
					<SkillGroupEditor
						bind:item={() => entry, (value) => (section.skills[index] = value)}
						ondelete={() => section.skills.splice(index, 1)}
					/>
				{/snippet}
			</SortableList>
			<div>
				<Button size="sm" icon="new" onclick={() => section.skills.push(newSkillGroup())}>
					Add skill group
				</Button>
			</div>
		{:else if section.kind === 'certifications'}
			<SortableList
				bind:items={section.certifications}
				noun="certification"
				label="Certifications in {name}"
			>
				{#snippet row(entry, index)}
					<CertificationEditor
						bind:item={() => entry, (value) => (section.certifications[index] = value)}
						ondelete={() => section.certifications.splice(index, 1)}
					/>
				{/snippet}
			</SortableList>
			<div>
				<Button
					size="sm"
					icon="new"
					onclick={() => section.certifications.push(newCertification())}
				>
					Add certification
				</Button>
			</div>
		{:else}
			<BulletList bind:bullets={section.custom} label="Items in {name}" addLabel="Add item" />
		{/if}
	</div>
</section>

<ConfirmDialog
	bind:open={confirming}
	title="Delete section"
	message="The {name} section and its {count} {count === 1 ? 'entry' : 'entries'} will be removed."
	confirmLabel="Delete section"
	danger
	onconfirm={ondelete}
/>
