import { describe, expect, it } from 'vitest';
import { manifest } from '../src/manifest.ts';
import { JOB_SITE_PATTERNS, jobSite, matchesPattern } from '../src/sites.ts';

describe('manifest', () => {
	it('gives Chrome a service worker and a side panel', () => {
		const chrome = manifest('chrome', 'http://localhost:5173', '1.2.3');

		expect(chrome).toMatchObject({
			manifest_version: 3,
			version: '1.2.3',
			background: { service_worker: 'background.js' },
			side_panel: { default_path: 'sidepanel.html' }
		});
		expect(chrome['permissions']).toEqual(['storage', 'activeTab', 'scripting', 'sidePanel']);
		expect(chrome).not.toHaveProperty('sidebar_action');
	});

	it('gives Firefox a background script, a sidebar and an add-on id', () => {
		const firefox = manifest('firefox', 'https://cvitae.aduuna.dev', '1.2.3');

		expect(firefox).toMatchObject({
			background: { scripts: ['background.js'] },
			sidebar_action: { default_panel: 'sidepanel.html' },
			browser_specific_settings: { gecko: { id: 'extension@cvitae.aduuna.dev' } }
		});
		expect(firefox['permissions']).toEqual(['storage', 'activeTab', 'scripting']);
	});

	it('reads the app and the job sites, and runs the connect script on the connect page only', () => {
		const built = manifest('chrome', 'http://localhost:5173', '0.1.0') as {
			host_permissions: string[];
			content_scripts: { matches: string[]; js: string[] }[];
		};

		// Match patterns cannot name a port.
		expect(built.host_permissions[0]).toBe('http://localhost/*');
		expect(built.host_permissions).toEqual(expect.arrayContaining([...JOB_SITE_PATTERNS]));
		expect(built.content_scripts[0]).toMatchObject({
			matches: ['http://localhost/app/extension*'],
			js: ['connect.js']
		});
		expect(built.content_scripts[1]).toMatchObject({
			matches: JOB_SITE_PATTERNS,
			js: ['content.js']
		});
	});
});

describe('sites', () => {
	it('matches extension patterns', () => {
		expect(
			matchesPattern('https://boards.greenhouse.io/acme/jobs/1', 'https://*.greenhouse.io/*')
		).toBe(true);
		expect(matchesPattern('https://greenhouse.io/', 'https://*.greenhouse.io/*')).toBe(true);
		expect(matchesPattern('https://evilgreenhouse.io/', 'https://*.greenhouse.io/*')).toBe(false);
		expect(matchesPattern('http://jobs.lever.co/acme', 'https://*.lever.co/*')).toBe(false);
		expect(matchesPattern('https://jobs.ashbyhq.com/acme', 'https://jobs.ashbyhq.com/*')).toBe(
			true
		);
		expect(matchesPattern('nonsense', 'https://*/*')).toBe(false);
	});

	it('names the platform a page is on', () => {
		expect(jobSite('https://acme.wd5.myworkdayjobs.com/en-US/careers/job/123')).toBe('Workday');
		expect(jobSite('https://bloomberg.avature.net/careers/ApplicationMethods?jobId=1')).toBe(
			'Avature'
		);
		expect(jobSite('https://example.com/careers')).toBeNull();
	});
});
