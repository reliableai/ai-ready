"""
Tests for Session 1: Hello Software 3.0

These tests demonstrate different approaches to testing AI systems:

1. STRUCTURAL TESTS - Check the shape of responses (not empty, reasonable length)
2. PROPERTY TESTS - Check properties (latency bounds, format)
3. LLM-AS-JUDGE - Use an LLM to evaluate if responses make sense
4. EXACT MATCH (FAILING) - Show why testing exact outputs doesn't work

Run tests:
    uv run pytest labs/tests/test_session1.py -v

Run only fast tests (skip voice tests):
    uv run pytest labs/tests/test_session1.py -v -m "not slow"
"""

import time
from pathlib import Path

import pytest


# =============================================================================
# TEST 1: CHAT COMPLETION
# =============================================================================


class TestChatCompletion:
    """Tests for 1_chat.py - basic chat completion."""

    def test_returns_non_empty_response(self, client):
        """STRUCTURAL: Response should not be empty."""
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Say hello."}],
        )

        content = response.choices[0].message.content
        assert content is not None
        assert len(content) > 0

    def test_response_reasonable_length(self, client):
        """STRUCTURAL: Response should be reasonable length for the prompt."""
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "user", "content": "Explain Software 3.0 in one sentence."}
            ],
        )

        content = response.choices[0].message.content
        # One sentence should be < 500 characters
        assert len(content) < 500, f"Response too long: {len(content)} chars"

    def test_latency_acceptable(self, client):
        """PROPERTY: Response should arrive within reasonable time."""
        start = time.time()

        client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Say 'test'."}],
        )

        elapsed = time.time() - start
        assert elapsed < 30, f"Response too slow: {elapsed:.2f}s"

    @pytest.mark.xfail(reason="Exact match doesn't work with LLMs - this is expected to fail")
    def test_exact_match_fails(self, client):
        """
        EXACT MATCH: This test demonstrates WHY exact matching doesn't work.

        Even for simple questions, the model might respond:
        - "4"
        - "The answer is 4."
        - "2 + 2 = 4"
        - "Four."

        This test is marked as xfail (expected to fail) to make the point.
        """
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "What is 2+2? Reply with just the number."}],
        )

        content = response.choices[0].message.content
        assert content == "4"  # This will likely fail!


# =============================================================================
# TEST 2: STREAMING
# =============================================================================


class TestStreaming:
    """Tests for 2_streaming.py - streaming responses."""

    def test_stream_produces_chunks(self, client):
        """STRUCTURAL: Streaming should produce multiple chunks."""
        stream = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Count from 1 to 5."}],
            stream=True,
        )

        chunks = []
        for chunk in stream:
            if chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)

        assert len(chunks) > 1, "Expected multiple chunks from streaming"

    def test_stream_assembles_to_valid_response(self, client):
        """STRUCTURAL: Assembled chunks should form a valid response."""
        stream = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Say 'Hello, world!'"}],
            stream=True,
        )

        full_response = ""
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                full_response += content

        assert len(full_response) > 0
        # Should contain hello in some form
        assert "hello" in full_response.lower() or "hi" in full_response.lower()


# =============================================================================
# TEST 3: VOICE (LLM-AS-JUDGE)
# =============================================================================


class TestVoice:
    """
    Tests for 3_voice.py - voice pipeline.

    Since we can't easily test audio recording/playback in CI, we test:
    1. Transcription with a pre-recorded audio file
    2. Response generation
    3. TTS output

    We use LLM-AS-JUDGE to evaluate if the response is sensible.
    """

    def test_transcription_works(self, client, fixtures_path):
        """STRUCTURAL: Whisper should transcribe audio to text."""
        audio_path = fixtures_path / "test_audio.wav"

        if not audio_path.exists():
            pytest.skip("test_audio.wav not found - run generate_test_audio.py first")

        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )

        assert transcript.text is not None
        assert len(transcript.text) > 0

    def test_tts_produces_audio(self, client):
        """STRUCTURAL: TTS should produce audio bytes."""
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input="Hello, this is a test.",
        )

        # Response should have content
        audio_bytes = response.read()
        assert len(audio_bytes) > 0
        # MP3 files start with ID3 tag or frame sync (0xFF followed by 0xFB, 0xF3, or 0xF2)
        is_id3 = audio_bytes[:3] == b"ID3"
        is_frame_sync = audio_bytes[0] == 0xFF and audio_bytes[1] in (0xFB, 0xF3, 0xF2, 0xFA)
        assert is_id3 or is_frame_sync, f"Not a valid MP3: starts with {audio_bytes[:4]}"

    def test_voice_pipeline_coherent_llm_judge(self, client, fixtures_path):
        """
        LLM-AS-JUDGE: Evaluate if the voice pipeline produces sensible responses.

        This test:
        1. Transcribes a test audio file
        2. Gets an LLM response to the transcription
        3. Asks another LLM call to judge if the response is appropriate

        This introduces the concept of LLM-as-judge, which we'll explore
        deeply in Phase 2 (Evaluation).
        """
        audio_path = fixtures_path / "test_audio.wav"

        if not audio_path.exists():
            pytest.skip("test_audio.wav not found - run generate_test_audio.py first")

        # Step 1: Transcribe
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        user_input = transcript.text

        # Step 2: Get response
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Keep responses brief.",
                },
                {"role": "user", "content": user_input},
            ],
        )
        assistant_response = response.choices[0].message.content

        # Step 3: LLM-as-judge
        judgment = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"""You are evaluating a voice assistant's response.

User said: "{user_input}"
Assistant replied: "{assistant_response}"

Is this a sensible, relevant response to the user's input?
Consider: Does it address what the user asked? Is it coherent?

Answer with exactly one word: YES or NO""",
                }
            ],
            temperature=0,  # More deterministic for judging
        )

        judgment_text = judgment.choices[0].message.content.strip().upper()

        # Log for debugging
        print(f"\n  User input: {user_input}")
        print(f"  Assistant response: {assistant_response}")
        print(f"  LLM Judge says: {judgment_text}")

        assert "YES" in judgment_text, (
            f"LLM judge found response inappropriate.\n"
            f"Input: {user_input}\n"
            f"Response: {assistant_response}\n"
            f"Judgment: {judgment_text}"
        )
