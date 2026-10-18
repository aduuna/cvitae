/**
 * The templates pictured on the landing page. Each image in static/landing/ is a copy of
 * templates/<id>/preview.png; tests/landing-previews.test.ts keeps the copies current.
 */
export const landingTemplates = [
	{ id: 'classic', name: 'Classic' },
	{ id: 'compact', name: 'Compact' },
	{ id: 'modern', name: 'Modern' },
	{ id: 'minimal', name: 'Minimal' },
	{ id: 'technical', name: 'Technical' }
] as const;
