import { CONNECT_PATH } from '../../web/src/lib/extension/protocol.ts';
import { JOB_SITE_PATTERNS } from './sites.ts';

export type Target = 'chrome' | 'firefox';

const NAME = 'Chameleon vitae';
const DESCRIPTION =
	'Fill job applications from your Chameleon vitae profile, attach a tailored CV and save job ads to tailor for.';
const ICONS = { 16: 'icons/16.png', 32: 'icons/32.png', 48: 'icons/48.png', 128: 'icons/128.png' };

/** A match pattern for the app's origin. Patterns cannot name a port, and match every port. */
function appPattern(appUrl: string, path = '/*'): string {
	const url = new URL(appUrl);
	return `${url.protocol}//${url.hostname}${path}`;
}

/** manifest.json for one browser. The two differ in the background script and the panel. */
export function manifest(target: Target, appUrl: string, version: string): Record<string, unknown> {
	const permissions = ['storage', 'activeTab', 'scripting'];
	const common = {
		manifest_version: 3,
		name: NAME,
		description: DESCRIPTION,
		version,
		icons: ICONS,
		action: { default_title: NAME, default_icon: ICONS },
		host_permissions: [appPattern(appUrl), ...JOB_SITE_PATTERNS],
		// Asked for one site at a time, from the side panel, when the user allows a site.
		optional_host_permissions: ['https://*/*', 'http://*/*'],
		content_scripts: [
			{
				// Only the page that hands over the token; the script checks the exact origin.
				matches: [appPattern(appUrl, `${CONNECT_PATH}*`)],
				js: ['connect.js'],
				run_at: 'document_start'
			},
			{
				matches: JOB_SITE_PATTERNS,
				js: ['content.js'],
				run_at: 'document_idle',
				all_frames: true
			}
		]
	};
	if (target === 'chrome') {
		return {
			...common,
			permissions: [...permissions, 'sidePanel'],
			background: { service_worker: 'background.js' },
			side_panel: { default_path: 'sidepanel.html' },
			minimum_chrome_version: '116'
		};
	}
	return {
		...common,
		permissions,
		background: { scripts: ['background.js'] },
		sidebar_action: {
			default_panel: 'sidepanel.html',
			default_title: NAME,
			default_icon: ICONS,
			open_at_install: false
		},
		browser_specific_settings: {
			gecko: {
				id: 'extension@cvitae.aduuna.dev',
				strict_min_version: '140.0',
				data_collection_permissions: {
					required: ['personallyIdentifyingInfo', 'websiteContent']
				}
			},
			// Firefox for Android reads data_collection_permissions from 142.
			gecko_android: { strict_min_version: '142.0' }
		}
	};
}
