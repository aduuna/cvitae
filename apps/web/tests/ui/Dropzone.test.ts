import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Dropzone, { DEFAULT_MAX_BYTES, validateUpload } from '#lib/components/ui/Dropzone.svelte';

const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

function makeFile(name: string, type: string, size = 2048): File {
	const file = new File(['x'], name, { type });
	Object.defineProperty(file, 'size', { value: size });
	return file;
}

function choose(input: HTMLInputElement, file: File) {
	Object.defineProperty(input, 'files', { value: [file], configurable: true });
	return fireEvent.change(input);
}

describe('validateUpload', () => {
	it('accepts PDF and DOCX by extension or type', () => {
		expect(validateUpload(makeFile('cv.pdf', 'application/pdf'), DEFAULT_MAX_BYTES)).toBeNull();
		expect(validateUpload(makeFile('CV.DOCX', ''), DEFAULT_MAX_BYTES)).toBeNull();
		expect(validateUpload(makeFile('cv', DOCX), DEFAULT_MAX_BYTES)).toBeNull();
	});

	it('rejects other types', () => {
		expect(validateUpload(makeFile('cv.txt', 'text/plain'), DEFAULT_MAX_BYTES)).toBe(
			'This file type is not supported. Choose a PDF or DOCX file.'
		);
	});

	it('rejects files over the limit', () => {
		const big = makeFile('cv.pdf', 'application/pdf', DEFAULT_MAX_BYTES + 1);
		expect(validateUpload(big, DEFAULT_MAX_BYTES)).toBe(
			'This file is larger than 10 MB. Choose a smaller file.'
		);
	});
});

describe('Dropzone', () => {
	function setup() {
		const onfile = vi.fn();
		render(Dropzone, { file: null, onfile });
		return {
			onfile,
			zone: screen.getByRole('group', { name: 'CV file' }),
			input: screen.getByTestId('dropzone-input') as HTMLInputElement
		};
	}

	it('invites a drop or a choice, accepting PDF and DOCX only', () => {
		const { zone, input } = setup();
		expect(zone).toHaveClass('border-dashed', 'border-line-strong');
		expect(zone).toHaveTextContent('Drop a PDF or DOCX file here');
		expect(zone).toHaveTextContent('Up to 10 MB');
		expect(input.accept).toContain('.pdf');
		expect(input.accept).toContain('.docx');
		expect(screen.getByRole('button', { name: 'Choose file' })).toBeInTheDocument();
	});

	it('opens the file picker from the button', async () => {
		const { input } = setup();
		const click = vi.spyOn(input, 'click');
		await userEvent.click(screen.getByRole('button', { name: 'Choose file' }));
		expect(click).toHaveBeenCalledOnce();
	});

	it('shows the chosen file name and size in mono', async () => {
		const { input, onfile } = setup();
		const file = makeFile('Ada-CV.pdf', 'application/pdf', 345_678);
		await choose(input, file);
		expect(onfile).toHaveBeenCalledWith(file);
		expect(screen.getByText('Ada-CV.pdf')).toBeInTheDocument();
		expect(screen.getByText('338 KB')).toHaveClass('font-mono', 'text-sm');
	});

	it('accepts a dropped file and highlights while dragging over', async () => {
		const { zone, onfile } = setup();
		const file = makeFile('cv.docx', DOCX);
		await fireEvent.dragOver(zone);
		expect(zone).toHaveAttribute('data-over');
		await fireEvent.drop(zone, { dataTransfer: { files: [file] } });
		expect(zone).not.toHaveAttribute('data-over');
		expect(onfile).toHaveBeenCalledWith(file);
		expect(screen.getByText('cv.docx')).toBeInTheDocument();
	});

	it('explains why a file was rejected', async () => {
		const { input, onfile, zone } = setup();
		await choose(input, makeFile('photo.png', 'image/png'));
		expect(screen.getByRole('alert')).toHaveTextContent(
			'This file type is not supported. Choose a PDF or DOCX file.'
		);
		expect(zone).toHaveClass('border-danger');
		expect(zone).toHaveAccessibleDescription(/not supported/);
		expect(onfile).not.toHaveBeenCalled();
	});

	it('removes the chosen file', async () => {
		const { input, onfile } = setup();
		await choose(input, makeFile('cv.pdf', 'application/pdf'));
		await userEvent.click(screen.getByRole('button', { name: 'Remove file' }));
		expect(onfile).toHaveBeenLastCalledWith(null);
		expect(screen.queryByText('cv.pdf')).toBeNull();
		expect(screen.getByRole('button', { name: 'Choose file' })).toBeInTheDocument();
	});
});
