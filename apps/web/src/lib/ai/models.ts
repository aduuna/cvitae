import type { SelectOption } from '#lib/components/ui/Select.svelte';
import type { AiModel, AiModelInfo } from '#lib/cv/types.ts';

/** The models as select options. With plans enforced, Pro models are disabled for Free users. */
export function modelOptions(
	models: AiModelInfo[],
	options: { plan?: 'free' | 'pro'; enforced?: boolean } = {}
): SelectOption[] {
	return models.map((model) => ({
		value: model.id,
		label: model.plan === 'pro' ? `${model.label} (Pro)` : model.label,
		disabled: Boolean(options.enforced && model.plan === 'pro' && options.plan !== 'pro')
	}));
}

/** The user's model while it is offered, else the server's default, else the first offered. */
export function pickModel(
	preferred: AiModel | null | undefined,
	models: AiModelInfo[],
	fallback: AiModel | null
): AiModel | null {
	for (const candidate of [preferred, fallback]) {
		if (candidate && models.some((model) => model.id === candidate)) return candidate;
	}
	return models[0]?.id ?? null;
}

export function modelLabel(id: AiModel, models: AiModelInfo[]): string {
	return models.find((model) => model.id === id)?.label ?? id;
}

/** Every offered model except `current`, for "Regenerate with". */
export function otherModels(current: AiModel, models: AiModelInfo[]): AiModelInfo[] {
	return models.filter((model) => model.id !== current);
}
