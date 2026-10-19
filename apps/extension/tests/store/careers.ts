/**
 * A careers page for a made-up employer, for the store screenshots: a job ad beside its
 * application form, with the field markup real job sites use. Its own plain look, so it reads as
 * someone else's site next to the extension.
 */
export function careersPage(job = 'Data Engineer'): string {
	const posting = {
		'@context': 'https://schema.org',
		'@type': 'JobPosting',
		title: job,
		hiringOrganization: { '@type': 'Organization', name: 'Harbour Bank' },
		description:
			'<p>Build the streaming and batch pipelines behind our fraud and payments teams.</p><ul><li>Spark, Kafka and Airflow in production</li><li>Own pipelines from ingestion to the dashboards people use</li><li>Work with analysts and engineers across the bank</li></ul>'
	};
	const months = [
		'January',
		'February',
		'March',
		'April',
		'May',
		'June',
		'July',
		'August',
		'September',
		'October',
		'November',
		'December'
	]
		.map((month, i) => `<option value="${i + 1}">${month}</option>`)
		.join('');
	const field = (id: string, label: string, attributes = '') =>
		`<div class="field"><label for="${id}">${label}</label><input id="${id}" ${attributes}></div>`;
	return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>${job} - Harbour Bank careers</title>
<script type="application/ld+json">${JSON.stringify(posting)}</script>
<style>
	* { box-sizing: border-box; }
	body { margin: 0; font: 14px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif; color: #1f2933; background: #f7f8fa; }
	.top { display: flex; align-items: center; justify-content: space-between; height: 52px; padding: 0 28px; background: #0b3b4f; color: #fff; }
	.brand { font-weight: 700; letter-spacing: 0.02em; }
	.top nav { font-size: 13px; opacity: 0.85; }
	.wrap { display: grid; grid-template-columns: 250px 1fr; gap: 28px; padding: 24px 28px; }
	.job h1 { margin: 6px 0 4px; font-size: 22px; }
	.crumb, .meta { margin: 0; color: #616e7c; font-size: 13px; }
	.job h2 { margin: 18px 0 6px; font-size: 14px; }
	.job p, .job li { color: #3e4c59; font-size: 13px; }
	.job ul { padding-left: 18px; margin: 0; }
	form { background: #fff; border: 1px solid #e4e7eb; border-radius: 6px; padding: 18px 20px; }
	form h2 { margin: 0 0 12px; font-size: 16px; }
	.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; }
	.field { display: flex; flex-direction: column; gap: 4px; }
	.field.wide { grid-column: 1 / -1; }
	label { font-size: 12px; font-weight: 600; color: #3e4c59; }
	input, select, textarea { font: inherit; padding: 7px 9px; border: 1px solid #cbd2d9; border-radius: 4px; background: #fff; color: #1f2933; }
	fieldset { border: 0; border-top: 1px solid #e4e7eb; margin: 14px 0 0; padding: 12px 0 0; }
	legend { padding: 0; font-weight: 700; font-size: 13px; margin-bottom: 8px; }
	.check { display: flex; align-items: center; gap: 6px; font-size: 13px; }
	.submit { margin-top: 16px; padding: 9px 16px; border: 0; border-radius: 4px; background: #0b3b4f; color: #fff; font-weight: 600; }
</style></head>
<body>
	<header class="top"><span class="brand">HARBOUR BANK</span><nav>Careers</nav></header>
	<div class="wrap">
		<section class="job">
			<p class="crumb">Careers / Engineering</p>
			<h1>${job}</h1>
			<p class="meta">London, UK - Full time - Hybrid</p>
			<h2>About the role</h2>
			<p>Build the streaming and batch pipelines behind our fraud and payments teams.</p>
			<ul>
				<li>Spark, Kafka and Airflow in production</li>
				<li>Own pipelines end to end</li>
				<li>Work with analysts across the bank</li>
			</ul>
		</section>
		<form>
			<h2>Apply for this job</h2>
			<div class="grid">
				${field('first_name', 'First name')}
				${field('last_name', 'Last name')}
				${field('email', 'Email', 'type="email"')}
				${field('phone', 'Phone', 'type="tel"')}
				${field('location', 'Location (city)')}
				${field('linkedin', 'LinkedIn profile')}
			</div>
			<fieldset>
				<legend>Employment</legend>
				<div class="grid">
					${field('company', 'Company name')}
					${field('title', 'Title')}
					<div class="field"><label for="start-month">Start date month</label><select id="start-month"><option value="">Select</option>${months}</select></div>
					${field('start-year', 'Start date year', 'type="number"')}
					<label class="check"><input type="checkbox" id="current"> Current role</label>
				</div>
			</fieldset>
			<fieldset>
				<legend>Education</legend>
				<div class="grid">
					${field('school', 'School')}
					${field('degree', 'Degree')}
				</div>
			</fieldset>
			<fieldset>
				<div class="field wide"><label for="resume">Resume/CV</label><input id="resume" type="file" accept=".pdf"></div>
				<div class="field wide" style="margin-top:10px"><label for="why">Why do you want to join us?</label><textarea id="why" rows="2"></textarea></div>
			</fieldset>
			<button class="submit" type="button">Submit application</button>
		</form>
	</div>
</body></html>`;
}
