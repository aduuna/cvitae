import type { CvContent, PlaceholderRef } from './types.ts';

/** Where a placeholder sits, for people: "Summary", or "Experience, Northwind Consulting". */
export function describeLocation(content: CvContent, ref: PlaceholderRef): string {
	if (!ref.bullet_id) return 'Summary';
	const id = ref.bullet_id;
	for (const section of content.sections) {
		const title = section.title || 'Untitled section';
		for (const role of section.experience) {
			if (role.bullets.some((bullet) => bullet.id === id))
				return place(title, role.org || role.role);
			for (const engagement of role.engagements) {
				if (engagement.bullets.some((bullet) => bullet.id === id)) {
					return place(title, engagement.name || role.org);
				}
			}
		}
		for (const project of section.projects) {
			if (project.bullets.some((bullet) => bullet.id === id)) return place(title, project.name);
		}
		if (section.custom.some((bullet) => bullet.id === id)) return title;
	}
	return 'A bullet that no longer exists';
}

function place(section: string, item: string): string {
	return item ? `${section}, ${item}` : section;
}
