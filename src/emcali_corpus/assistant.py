"""Orquestación de tareas de LLM (Q&A, Resumen y FAQ) con LangChain y DeepSeek."""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_deepseek import ChatDeepSeek

from emcali_corpus.knowledge import KnowledgeBaseBundle
from emcali_corpus.prompts import (
    DEFAULT_STRATEGY_KEY,
    build_faq_prompt,
    build_qa_system_prompt,
    build_summary_prompt,
)

DEFAULT_MODEL = "deepseek-flash"
DEFAULT_TEMPERATURE = 0.0
REASONING_EFFORTS = ("low", "high", "max")


class MissingAPIKeyError(RuntimeError):
    """Se lanza cuando DEEPSEEK_API_KEY no está configurada en el entorno."""


@dataclass(frozen=True, slots=True)
class AssistantSettings:
    """Configuración de ejecución para el modelo DeepSeek en LangChain."""

    api_key: str
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    reasoning_effort: str | None = None


@dataclass(frozen=True, slots=True)
class AssistantReply:
    """Respuesta estructurada devuelta por cualquiera de las tareas del asistente."""

    answer: str
    reasoning: str
    model: str
    strategy_key: str
    context_documents: int
    context_words: int


def load_assistant_settings(
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    reasoning_effort: str | None = None,
) -> AssistantSettings:
    """Carga y valida la configuración del modelo desde variables de entorno o .env."""
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise MissingAPIKeyError(
            "No se encontró DEEPSEEK_API_KEY. Agrégala en el archivo .env "
            "(DEEPSEEK_API_KEY=sk-...) o expórtala en tu terminal."
        )
    if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(
            f"reasoning_effort={reasoning_effort!r} no es válido. "
            f"Usa uno de: {', '.join(REASONING_EFFORTS)}."
        )
    return AssistantSettings(
        api_key=api_key,
        model=model,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
    )


def build_chat_model(settings: AssistantSettings | None = None) -> ChatDeepSeek:
    """Inicializa el modelo ChatDeepSeek con los parámetros indicados."""
    resolved = settings or load_assistant_settings()
    kwargs: dict[str, Any] = {
        "model": resolved.model,
        "api_key": resolved.api_key,
        "temperature": resolved.temperature,
    }
    if resolved.reasoning_effort is not None:
        kwargs["reasoning_effort"] = resolved.reasoning_effort
    return ChatDeepSeek(**kwargs)


def extract_message_parts(
    message: BaseMessage | AIMessage | AIMessageChunk | Any,
) -> tuple[str, str]:
    """Separa el contenido de un mensaje o chunk de LangChain en (texto, razonamiento)."""
    text_parts: list[str] = []
    reasoning_parts: list[str] = []

    content = getattr(message, "content", "")
    if isinstance(content, str):
        text_parts.append(content)
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(str(block.get("text", "")))
            elif block_type in {"reasoning", "thinking"}:
                thought = block.get("reasoning") or block.get("thinking") or ""
                reasoning_parts.append(str(thought))

    additional = getattr(message, "additional_kwargs", None)
    if isinstance(additional, dict) and not reasoning_parts:
        extra_reasoning = additional.get("reasoning_content")
        if isinstance(extra_reasoning, str) and extra_reasoning:
            reasoning_parts.append(extra_reasoning)

    return "".join(text_parts), "".join(reasoning_parts)


def build_qa_agent(
    bundle: KnowledgeBaseBundle,
    *,
    settings: AssistantSettings | None = None,
    strategy_key: str = DEFAULT_STRATEGY_KEY,
    custom_instructions: str | None = None,
) -> Any:
    """Construye el agente Q&A en LangChain con la base de conocimiento en el system prompt."""
    resolved = settings or load_assistant_settings()
    system_prompt = build_qa_system_prompt(
        bundle.consolidated_text,
        strategy_key=strategy_key,
        custom_instructions=custom_instructions,
    )
    return create_agent(
        model=build_chat_model(resolved),
        tools=[],
        system_prompt=system_prompt,
    )


def _run_prompt_chain(
    system_prompt: str,
    user_prompt: str,
    *,
    settings: AssistantSettings | None = None,
    chat_model: Any | None = None,
) -> tuple[str, str, str]:
    """Ejecuta una cadena LCEL (ChatPromptTemplate | ChatDeepSeek) y extrae la respuesta."""
    resolved = settings or load_assistant_settings()
    model = chat_model or build_chat_model(resolved)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "{system_prompt}"),
            ("human", "{user_prompt}"),
        ]
    )
    chain = prompt | model
    response = chain.invoke(
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }
    )
    answer, reasoning = extract_message_parts(response)
    return answer.strip(), reasoning.strip(), resolved.model


def answer_question(
    question: str,
    bundle: KnowledgeBaseBundle,
    *,
    settings: AssistantSettings | None = None,
    strategy_key: str = DEFAULT_STRATEGY_KEY,
    custom_instructions: str | None = None,
    history: Sequence[dict[str, str]] | None = None,
    chat_model: Any | None = None,
) -> AssistantReply:
    """Responde una pregunta del usuario basándose estrictamente en el corpus consolidado."""
    if not question.strip():
        raise ValueError("La pregunta no puede estar vacía.")

    system_prompt = build_qa_system_prompt(
        bundle.consolidated_text,
        strategy_key=strategy_key,
        custom_instructions=custom_instructions,
    )
    if history:
        turns = "\n".join(
            f"{'Usuario' if item.get('role') == 'user' else 'Asistente'}: {item.get('content', '')}"
            for item in history
        )
        user_prompt = (
            f"Historial reciente de la conversación:\n{turns}\n\n"
            f"Pregunta actual del usuario:\n{question.strip()}"
        )
    else:
        user_prompt = question.strip()

    answer, reasoning, model_name = _run_prompt_chain(
        system_prompt,
        user_prompt,
        settings=settings,
        chat_model=chat_model,
    )
    return AssistantReply(
        answer=answer,
        reasoning=reasoning,
        model=model_name,
        strategy_key=strategy_key,
        context_documents=bundle.document_count,
        context_words=bundle.total_words,
    )


def stream_question(
    question: str,
    bundle: KnowledgeBaseBundle,
    *,
    settings: AssistantSettings | None = None,
    strategy_key: str = DEFAULT_STRATEGY_KEY,
    custom_instructions: str | None = None,
    history: Sequence[dict[str, str]] | None = None,
) -> Iterator[tuple[str, str]]:
    """Transmite en streaming (texto, razonamiento) la respuesta del agente Q&A."""
    agent = build_qa_agent(
        bundle,
        settings=settings,
        strategy_key=strategy_key,
        custom_instructions=custom_instructions,
    )
    messages = [*(history or []), {"role": "user", "content": question.strip()}]
    for chunk, _metadata in agent.stream(
        {"messages": messages},
        stream_mode="messages",
    ):
        if isinstance(chunk, AIMessageChunk):
            text, thought = extract_message_parts(chunk)
            if text or thought:
                yield text, thought


def generate_summary(
    bundle: KnowledgeBaseBundle,
    *,
    settings: AssistantSettings | None = None,
    focus_topic: str = "",
    chat_model: Any | None = None,
) -> AssistantReply:
    """Genera un resumen ejecutivo estructurado del corpus consolidado."""
    system_prompt, user_prompt = build_summary_prompt(
        bundle.consolidated_text,
        focus_topic=focus_topic,
    )
    answer, reasoning, model_name = _run_prompt_chain(
        system_prompt,
        user_prompt,
        settings=settings,
        chat_model=chat_model,
    )
    return AssistantReply(
        answer=answer,
        reasoning=reasoning,
        model=model_name,
        strategy_key="estricto_citado",
        context_documents=bundle.document_count,
        context_words=bundle.total_words,
    )


def generate_faq(
    bundle: KnowledgeBaseBundle,
    *,
    settings: AssistantSettings | None = None,
    num_questions: int = 8,
    focus_topic: str = "",
    chat_model: Any | None = None,
) -> AssistantReply:
    """Genera un listado de Preguntas Frecuentes (FAQ) verificadas a partir del contexto."""
    system_prompt, user_prompt = build_faq_prompt(
        bundle.consolidated_text,
        num_questions=num_questions,
        focus_topic=focus_topic,
    )
    answer, reasoning, model_name = _run_prompt_chain(
        system_prompt,
        user_prompt,
        settings=settings,
        chat_model=chat_model,
    )
    return AssistantReply(
        answer=answer,
        reasoning=reasoning,
        model=model_name,
        strategy_key="estricto_citado",
        context_documents=bundle.document_count,
        context_words=bundle.total_words,
    )
