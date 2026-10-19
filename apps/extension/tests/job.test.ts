import { describe, expect, it } from 'vitest';
import { cleanUrl, findPosting, htmlToText, readJob } from '../src/content/job.ts';

function addPosting(data: unknown): void {
	const script = document.createElement('script');
	script.type = 'application/ld+json';
	script.textContent = JSON.stringify(data);
	document.head.append(script);
}

const posting = {
	'@context': 'https://schema.org',
	'@type': 'JobPosting',
	title: 'Senior Data Engineer',
	hiringOrganization: { '@type': 'Organization', name: 'Harbour Bank' },
	description: '<p>Build pipelines.</p><ul><li>Spark</li><li>Kafka</li></ul>'
};

describe('readJob', () => {
	it('reads the job posting data job boards publish for search engines', () => {
		addPosting(posting);
		document.body.innerHTML = '<h1>Ignored heading</h1>';

		expect(readJob()).toEqual({
			title: 'Senior Data Engineer',
			company: 'Harbour Bank',
			url: 'http://localhost:3000/',
			description: 'Build pipelines.\n- Spark\n- Kafka',
			from: 'posting'
		});
	});

	it('finds a posting inside a graph or a list', () => {
		addPosting({ '@graph': [{ '@type': 'WebPage' }, [{ ...posting, title: 'In a graph' }]] });

		expect(findPosting(document)?.['title']).toBe('In a graph');
	});

	it('decodes a description that was escaped twice', () => {
		addPosting({ ...posting, description: '&lt;p&gt;Escaped &amp;amp; nested&lt;/p&gt;' });

		expect(readJob()?.description).toBe('Escaped & nested');
	});

	it('uses the selected text when there is no posting data', () => {
		document.body.innerHTML = `<h1>Data engineer</h1><p id="ad">${'We are hiring. '.repeat(20)}</p>`;
		const range = document.createRange();
		range.selectNodeContents(document.getElementById('ad')!);
		document.getSelection()!.addRange(range);

		const job = readJob();

		expect(job?.from).toBe('selection');
		expect(job?.title).toBe('Data engineer');
		document.getSelection()!.removeAllRanges();
	});

	it('falls back to the main content, without the application form', () => {
		document.body.innerHTML = `
			<nav>Jobs</nav>
			<main>
				<h1>Platform engineer</h1>
				<p>Run our clusters.</p>
				<form><label>First name</label><input></form>
			</main>`;

		expect(readJob()).toMatchObject({
			title: 'Platform engineer',
			description: 'Platform engineer\nRun our clusters.',
			from: 'page'
		});
	});

	it('reads a page that wraps everything in a form', () => {
		document.body.innerHTML = '<form><main><p>Whole site in a form.</p></main></form>';
		expect(readJob()?.description).toBe('Whole site in a form.');

		document.body.innerHTML = '<form><div><p>No main element either.</p></div></form>';
		expect(readJob()?.description).toBe('No main element either.');
	});

	it("takes the company from a job board's path before the site's name", () => {
		const meta = document.createElement('meta');
		meta.setAttribute('property', 'og:site_name');
		meta.setAttribute('content', 'Job board');
		document.head.append(meta);
		document.body.innerHTML = '<main><h1>Data engineer</h1><p>Pipelines.</p></main>';
		window.history.pushState({}, '', '/');
		const canonical = document.createElement('link');
		canonical.rel = 'canonical';
		canonical.href = 'https://jobs.lever.co/harbour-bank/0d2c9a10-1b2c-4d5e-8f90-a1b2c3d4e5f6';
		document.head.append(canonical);

		expect(readJob()?.company).toBe('Harbour Bank');

		canonical.remove();
		expect(readJob()?.company).toBe('Job board');
	});

	it('gives nothing for an empty page', () => {
		expect(readJob()).toBeNull();
	});
});

describe('htmlToText', () => {
	it('keeps paragraphs and list items on their own lines', () => {
		expect(htmlToText('<h2>About</h2><p>One<br>two</p><ol><li>A</li></ol><script>x</script>')).toBe(
			'About\nOne\ntwo\n- A'
		);
	});
});

describe('cleanUrl', () => {
	it('drops the fragment and tracking parameters, keeping the job id', () => {
		expect(
			cleanUrl('https://acme.com/careers/job?gh_jid=123&gh_src=abc&utm_source=li&lang=en#app')
		).toBe('https://acme.com/careers/job?gh_jid=123&lang=en');
	});
});
