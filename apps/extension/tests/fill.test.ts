import { act, createElement, useState, type ChangeEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import { element, scan } from '../src/content/fields.ts';
import { attachFile, fillFields, undoFill, write } from '../src/content/fill.ts';
import { planFill } from '../src/content/plan.ts';
import { loadFixture, sampleData } from './helpers.ts';

declare global {
	var IS_REACT_ACT_ENVIRONMENT: boolean;
}

describe('write', () => {
	it('fires the events a user typing fires', () => {
		document.body.innerHTML = '<input id="a">';
		const input = document.querySelector('input')!;
		const seen: string[] = [];
		for (const type of ['focusin', 'input', 'change', 'focusout']) {
			input.addEventListener(type, () => seen.push(type));
		}

		write(input, 'Ama');

		expect(input.value).toBe('Ama');
		expect(seen).toEqual(['focusin', 'input', 'change', 'focusout']);
	});

	it('chooses an option and ticks a box with a click', () => {
		document.body.innerHTML =
			'<select><option value="">-</option><option value="GB">UK</option></select><input type="checkbox">';
		const select = document.querySelector('select')!;
		const box = document.querySelector<HTMLInputElement>('input')!;
		const clicked = vi.fn();
		box.addEventListener('click', clicked);

		write(select, 'GB');
		write(box, 'true');
		write(box, 'true');

		expect(select.value).toBe('GB');
		expect(box.checked).toBe(true);
		expect(clicked).toHaveBeenCalledOnce();
	});
});

describe('fillFields', () => {
	it('fills the planned fields, marks them, and undoes', () => {
		loadFixture('lever');
		const page = scan();
		const plan = planFill(page.fields, sampleData());

		const count = fillFields(plan.assignments, element);

		// Name, email, phone, location, company, LinkedIn and GitHub: the sample has no Twitter or site.
		expect(count).toBe(7);
		const name = document.querySelector<HTMLInputElement>('input[name="name"]')!;
		expect(name.value).toBe('Ama Owusu-Mensah');
		expect(name).toHaveAttribute('data-cvitae-filled');
		expect(document.querySelector<HTMLInputElement>('input[name="org"]')!.value).toBe(
			'Northwind Consulting'
		);
		expect(document.getElementById('cvitae-filled-style')).not.toBeNull();

		// Typing in a field clears its mark.
		name.dispatchEvent(new KeyboardEvent('keydown'));
		expect(name).not.toHaveAttribute('data-cvitae-filled');

		expect(undoFill()).toBe(7);
		expect(name.value).toBe('');
		expect(undoFill()).toBe(0);
	});

	it('skips fields that are gone', () => {
		document.body.innerHTML = '<label for="e">Email</label><input id="e">';
		const [email] = scan().fields;
		document.body.innerHTML = '';

		expect(fillFields([{ fieldId: email!.id, value: 'x' }], element)).toBe(0);
	});
});

describe('attachFile', () => {
	it('refuses anything but a file input', () => {
		document.body.innerHTML = '<input type="text">';
		const file = { name: 'cv.pdf', type: 'application/pdf', base64: 'JVBERg==' };

		expect(attachFile(document.querySelector('input')!, file)).toBe(false);
		expect(attachFile(undefined, file)).toBe(false);
	});
});

/** A form like Greenhouse's or Ashby's: React owns the values and renders them back. */
function ReactForm({ onSubmit }: { onSubmit: (values: Record<string, string | boolean>) => void }) {
	const [values, setValues] = useState({ first: '', email: '', country: '', current: false });
	const text = (name: 'first' | 'email') => ({
		id: name,
		value: values[name],
		onChange: (event: ChangeEvent<HTMLInputElement>) =>
			setValues((v) => ({ ...v, [name]: event.target.value }))
	});
	return createElement(
		'form',
		{
			onSubmit: (event: Event) => {
				event.preventDefault();
				onSubmit(values);
			}
		},
		createElement('label', { htmlFor: 'first' }, 'First name'),
		createElement('input', text('first')),
		createElement('label', { htmlFor: 'email' }, 'Email'),
		createElement('input', { ...text('email'), type: 'email' }),
		createElement('label', { htmlFor: 'country' }, 'Country'),
		createElement(
			'select',
			{
				id: 'country',
				value: values.country,
				onChange: (event: ChangeEvent<HTMLSelectElement>) =>
					setValues((v) => ({ ...v, country: event.target.value }))
			},
			createElement('option', { value: '' }, 'Select'),
			createElement('option', { value: 'GB' }, 'United Kingdom')
		),
		createElement('h3', null, 'Employment'),
		createElement('input', {
			id: 'current',
			type: 'checkbox',
			checked: values.current,
			onChange: (event: ChangeEvent<HTMLInputElement>) =>
				setValues((v) => ({ ...v, current: event.target.checked }))
		}),
		createElement('label', { htmlFor: 'current' }, 'I currently work here'),
		createElement('button', { type: 'submit' }, 'Submit')
	);
}

describe('filling a React form', () => {
	it('updates React state, not just the DOM', async () => {
		globalThis.IS_REACT_ACT_ENVIRONMENT = true;
		const container = document.createElement('div');
		document.body.append(container);
		const submitted = vi.fn();
		const root = createRoot(container);
		await act(async () => root.render(createElement(ReactForm, { onSubmit: submitted })));

		const plan = planFill(scan().fields, sampleData());
		await act(async () => {
			fillFields(plan.assignments, element);
		});
		await act(async () => {
			document.querySelector('form')!.requestSubmit();
		});

		expect(submitted).toHaveBeenCalledWith({
			first: 'Ama',
			email: 'ama@example.com',
			country: 'GB',
			current: true
		});
		await act(async () => root.unmount());
	});
});
