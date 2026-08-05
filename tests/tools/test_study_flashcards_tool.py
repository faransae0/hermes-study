"""Tests for tools/study_flashcards_tool.py's generate_flashcards()."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tools.study_flashcards_tool import generate_flashcards


@pytest.mark.asyncio
async def test_generate_flashcards_success():
    fake_llm_json = json.dumps(
        {
            "cards": [
                {"front": "What is inertia?", "back": "Resistance to changes in motion."},
                {"front": "Who formulated the laws of motion?", "back": "Isaac Newton."},
            ]
        }
    )
    fake_message = type("Msg", (), {"content": fake_llm_json})
    fake_choice = type("Choice", (), {"message": fake_message})
    fake_response = type("Response", (), {"choices": [fake_choice]})

    with patch("agent.auxiliary_client.call_llm", return_value=fake_response) as mock_call_llm:
        result = await generate_flashcards("Newton's laws of motion...", "Physics 101")

    assert result["success"] is True
    assert len(result["cards"]) == 2
    assert result["cards"][0] == {"front": "What is inertia?", "back": "Resistance to changes in motion."}
    assert mock_call_llm.call_args.kwargs["task"] == "study_flashcards"


@pytest.mark.asyncio
async def test_generate_flashcards_empty_text():
    result = await generate_flashcards("", "Some Title")
    assert result["success"] is False
    assert "No text" in result["error"]


@pytest.mark.asyncio
async def test_generate_flashcards_llm_call_failure():
    with patch("agent.auxiliary_client.call_llm", side_effect=RuntimeError("no provider configured")):
        result = await generate_flashcards("some text", "Some Title")

    assert result["success"] is False
    assert "no provider configured" in result["error"]


@pytest.mark.asyncio
async def test_generate_flashcards_llm_non_json_response():
    fake_message = type("Msg", (), {"content": "not json"})
    fake_choice = type("Choice", (), {"message": fake_message})
    fake_response = type("Response", (), {"choices": [fake_choice]})

    with patch("agent.auxiliary_client.call_llm", return_value=fake_response):
        result = await generate_flashcards("some text", "Some Title")

    assert result["success"] is False
    assert "non-JSON" in result["error"]


@pytest.mark.asyncio
async def test_generate_flashcards_llm_returns_empty_card_list():
    fake_message = type("Msg", (), {"content": json.dumps({"cards": []})})
    fake_choice = type("Choice", (), {"message": fake_message})
    fake_response = type("Response", (), {"choices": [fake_choice]})

    with patch("agent.auxiliary_client.call_llm", return_value=fake_response):
        result = await generate_flashcards("some text", "Some Title")

    assert result["success"] is False
    assert "no flashcards" in result["error"].lower()


@pytest.mark.asyncio
async def test_generate_flashcards_filters_malformed_cards():
    fake_message = type(
        "Msg",
        (),
        {
            "content": json.dumps(
                {
                    "cards": [
                        {"front": "Valid Q", "back": "Valid A"},
                        {"front": "Missing back"},
                        {"back": "Missing front"},
                        "not even a dict",
                    ]
                }
            )
        },
    )
    fake_choice = type("Choice", (), {"message": fake_message})
    fake_response = type("Response", (), {"choices": [fake_choice]})

    with patch("agent.auxiliary_client.call_llm", return_value=fake_response):
        result = await generate_flashcards("some text", "Some Title")

    assert result["success"] is True
    assert result["cards"] == [{"front": "Valid Q", "back": "Valid A"}]


@pytest.mark.asyncio
async def test_generate_flashcards_filters_non_string_front_back():
    fake_message = type(
        "Msg",
        (),
        {
            "content": json.dumps(
                {
                    "cards": [
                        {"front": "Valid Q", "back": "Valid A"},
                        {"front": 123, "back": "numeric front"},
                        {"front": "nested back", "back": {"a": 1}},
                    ]
                }
            )
        },
    )
    fake_choice = type("Choice", (), {"message": fake_message})
    fake_response = type("Response", (), {"choices": [fake_choice]})

    with patch("agent.auxiliary_client.call_llm", return_value=fake_response):
        result = await generate_flashcards("some text", "Some Title")

    assert result["success"] is True
    assert result["cards"] == [{"front": "Valid Q", "back": "Valid A"}]


@pytest.mark.asyncio
async def test_generate_flashcards_llm_returns_non_object_json():
    fake_message = type("Msg", (), {"content": "42"})
    fake_choice = type("Choice", (), {"message": fake_message})
    fake_response = type("Response", (), {"choices": [fake_choice]})

    with patch("agent.auxiliary_client.call_llm", return_value=fake_response):
        result = await generate_flashcards("some text", "Some Title")

    assert result["success"] is False
    assert "error" in result
