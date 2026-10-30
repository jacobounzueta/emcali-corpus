"""Pruebas offline de ingeniería de prompts, asistente LangChain y evaluación Q&A."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from emcali_corpus.assistant import (
    AssistantSettings,
    answer_question,
    extract_message_parts,
    generate_faq,
    generate_summary,
)
from emcali_corpus.evaluation import BENCHMARK_QUESTIONS, evaluate_reply, render_benchmark_markdown
from emcali_corpus.knowledge import KnowledgeBaseBundle, KnowledgeDocument
from emcali_corpus.prompts import build_faq_prompt, build_qa_system_prompt, build_summary_prompt


def _dummy_bundle() -> KnowledgeBaseBundle:
    doc = KnowledgeDocument(
        slug="about",
        section="about",
        title="Sobre nosotros",
        source_url="https://www.emcali.com.co/about",
        description="Información corporativa.",
        body="# Sobre nosotros\n\nRoger Mina es el Gerente General de EMCALI.",
        word_count=10,
        content_sha256="abc123",
        gold_path="data/gold/about/about.md",
    )
    return KnowledgeBaseBundle(
        documents=(doc,),
        consolidated_text=doc.render_block(),
        sections=("about",),
    )


def test_build_prompts_contain_context_and_rules() -> None:
    # Arrange
    context = "## [ABOUT] Sobre nosotros\n Roger Mina — Gerente General"

    # Act
    qa_sys = build_qa_system_prompt(context, strategy_key="estricto_citado")
    sum_sys, sum_user = build_summary_prompt(context, focus_topic="Energía")
    faq_sys, faq_user = build_faq_prompt(context, num_questions=5, focus_topic="Pagos")

    # Assert
    assert "BASE DE CONOCIMIENTO OFICIAL" in qa_sys
    assert "Roger Mina" in qa_sys
    assert "Energía" in sum_user
    assert "5 Preguntas Frecuentes" in faq_user
    assert "EMCALI" in sum_sys
    assert "EMCALI" in faq_sys


def test_extract_message_parts_handles_blocks_and_strings() -> None:
    # Arrange
    msg_str = AIMessage(content="Respuesta directa")
    msg_blocks = AIMessage(
        content=[
            {"type": "reasoning", "reasoning": "Verificando documento about.md"},
            {"type": "text", "text": "El Gerente General es Roger Mina."},
        ]
    )

    # Act
    text_a, reason_a = extract_message_parts(msg_str)
    text_b, reason_b = extract_message_parts(msg_blocks)

    # Assert
    assert text_a == "Respuesta directa"
    assert reason_a == ""
    assert text_b == "El Gerente General es Roger Mina."
    assert "about.md" in reason_b


def test_assistant_tasks_with_mock_langchain_model() -> None:
    # Arrange
    bundle = _dummy_bundle()
    settings = AssistantSettings(api_key="sk-test-dummy", model="deepseek-flash")
    fake_llm = RunnableLambda(
        lambda _prompt_val: AIMessage(
            content=(
                "Roger Mina es el Gerente General.\n\n"
                "### Fuentes oficiales\n- [Sobre nosotros](https://www.emcali.com.co/about)"
            )
        )
    )

    # Act
    qa_reply = answer_question(
        "¿Quién es el Gerente General?",
        bundle,
        settings=settings,
        chat_model=fake_llm,
    )
    sum_reply = generate_summary(bundle, settings=settings, chat_model=fake_llm)
    faq_reply = generate_faq(bundle, settings=settings, num_questions=3, chat_model=fake_llm)

    # Assert
    assert "Roger Mina" in qa_reply.answer
    assert qa_reply.context_documents == 1
    assert "https://www.emcali.com.co/about" in sum_reply.answer
    assert "Roger Mina" in faq_reply.answer


def test_benchmark_has_at_least_twenty_questions_and_evaluates() -> None:
    # Arrange
    q1 = BENCHMARK_QUESTIONS[0]
    q_trap = BENCHMARK_QUESTIONS[-1]
    good_answer = (
        "El Gerente General es Roger Mina, junto a Mario Germán Ocaña, "
        "Diego Fernando Carabali y Roberto Carlos Angulo.\n"
        "Fuente: https://www.emcali.com.co/about"
    )
    refusal_answer = (
        "No cuento con esa información en la base de conocimiento pública oficial de EMCALI."
    )

    # Act
    ev1 = evaluate_reply(q1, good_answer)
    ev_trap = evaluate_reply(q_trap, refusal_answer)
    report_md = render_benchmark_markdown([ev1, ev_trap], context_docs=164, context_words=54625)

    # Assert
    assert len(BENCHMARK_QUESTIONS) >= 20
    assert ev1.passed is True
    assert ev1.has_source_citation is True
    assert ev_trap.passed is True
    assert "2/2 (100.0%)" in report_md
