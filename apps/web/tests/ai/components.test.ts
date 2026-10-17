import { act, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import GenerationProgress from '#lib/components/ai/GenerationProgress.svelte';
import ModelSelect from '#lib/components/ai/ModelSelect.svelte';
import type { AiModelInfo } from '#lib/cv/types.ts';
import RichText from '#lib/components/cv/RichText.svelte';

describe('GenerationProgress', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it('moves through the steps, counts seconds and cancels', async () => {
		const oncancel = vi.fn();
		render(GenerationProgress, {
			steps: ['Reading', 'Selecting', 'Writing'],
			stepSeconds: 2,
			caption: 'Tailoring with Claude',
			oncancel
		});

		expect(screen.getByText('Reading')).toHaveAttribute('aria-live', 'polite');
		expect(screen.getByRole('progressbar', { name: 'Working' })).toBeVisible();
		expect(
			screen.getByText(/Tailoring with Claude\. This can take 1 to 2 minutes\./)
		).toBeVisible();

		await act(() => vi.advanceTimersByTime(2100));
		expect(screen.getByText('Selecting')).toBeVisible();
		await act(() => vi.advanceTimersByTime(60_000));
		expect(screen.getByText('Writing')).toBeVisible();
		expect(screen.getByLabelText('62 seconds')).toHaveTextContent('62s');

		screen.getByRole('button', { name: 'Cancel' }).click();
		expect(oncancel).toHaveBeenCalledOnce();
	});
});

const MODELS: AiModelInfo[] = [
	{ id: 'mimo-flash', label: 'MiMo Flash', provider: 'mimo', plan: 'free' },
	{ id: 'claude-haiku', label: 'Claude Haiku', provider: 'claude', plan: 'free' },
	{ id: 'gemini-flash-lite', label: 'Gemini Flash-Lite', provider: 'gemini', plan: 'free' },
	{ id: 'mimo-pro', label: 'MiMo Pro', provider: 'mimo', plan: 'pro' },
	{ id: 'gemini-flash', label: 'Gemini Flash', provider: 'gemini', plan: 'pro' },
	{ id: 'claude-sonnet', label: 'Claude Sonnet', provider: 'claude', plan: 'pro' }
];

describe('ModelSelect', () => {
	it('lists every offered model, marking Pro ones', async () => {
		const user = userEvent.setup();
		render(ModelSelect, { value: 'mimo-flash', models: MODELS });

		const select = screen.getByLabelText('AI model');
		expect(select).toHaveValue('mimo-flash');
		expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
			'MiMo Flash',
			'Claude Haiku',
			'Gemini Flash-Lite',
			'MiMo Pro (Pro)',
			'Gemini Flash (Pro)',
			'Claude Sonnet (Pro)'
		]);
		await user.selectOptions(select, 'claude-sonnet');
		expect(select).toHaveValue('claude-sonnet');
		expect(screen.getByRole('option', { name: 'Claude Sonnet (Pro)' })).toBeEnabled();
	});

	it('disables Pro models for Free users once plans are enforced', () => {
		render(ModelSelect, { value: 'mimo-flash', models: MODELS, plan: 'free', enforced: true });

		expect(screen.getByRole('option', { name: 'Claude Sonnet (Pro)' })).toBeDisabled();
		expect(screen.getByRole('option', { name: 'Claude Haiku' })).toBeEnabled();
	});

	it('explains when no model is set up', () => {
		render(ModelSelect, { value: null, models: [] });

		expect(screen.getByText('AI is not set up on this server yet.')).toBeVisible();
		expect(screen.queryByRole('combobox')).toBeNull();
	});
});

describe('RichText', () => {
	it('renders bold and placeholders without markers', () => {
		const { container } = render(RichText, { text: 'Cut **40%** for [[number of teams]] teams' });

		expect(container).toHaveTextContent('Cut 40% for number of teams teams');
		expect(container.querySelector('strong')).toHaveTextContent('40%');
		expect(screen.getByText('number of teams').closest('.bg-placeholder')).not.toBeNull();
	});
});
