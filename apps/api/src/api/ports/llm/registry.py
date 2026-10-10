"""The configured providers and the AI models they make available."""

from api.ai.models import AiModel, ModelOption
from api.ports.llm.base import LLMProvider, ProviderName


class ProviderRegistry:
    def __init__(
        self, providers: dict[ProviderName, LLMProvider], options: list[ModelOption]
    ) -> None:
        self._providers = providers
        # A model is offered only when its provider has a key.
        self._options = {o.id: o for o in options if o.provider in providers}

    @property
    def options(self) -> list[ModelOption]:
        return list(self._options.values())

    def option(self, model: AiModel) -> ModelOption | None:
        return self._options.get(model)

    def provider(self, option: ModelOption) -> LLMProvider:
        return self._providers[option.provider]
