import type { IconName } from '#lib/components/ui/icons.ts';

export interface NavItem {
	label: string;
	href: '/app/documents' | '/app/profiles' | '/app/tailor' | '/app/templates' | '/app/settings';
	icon: IconName;
}

/** Side nav items in order (docs/PRODUCT.md, Navigation). */
export const navItems: readonly NavItem[] = [
	{ label: 'Documents', href: '/app/documents', icon: 'documents' },
	{ label: 'Profiles', href: '/app/profiles', icon: 'profiles' },
	{ label: 'Tailor', href: '/app/tailor', icon: 'tailor' },
	{ label: 'Templates', href: '/app/templates', icon: 'templates' },
	{ label: 'Settings', href: '/app/settings', icon: 'settings' }
];

export function isActive(item: NavItem, pathname: string): boolean {
	return pathname === item.href || pathname.startsWith(`${item.href}/`);
}
