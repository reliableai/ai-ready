"""
Generate test audio fixture for voice tests.

This script creates a test_audio.wav file using OpenAI's TTS API.
The audio contains a simple question that we can use to test the voice pipeline.

Run once to generate the fixture:
    uv run python tests/generate_test_audio.py
"""

from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
import soundfile as sf
import numpy as np
import io

load_dotenv()

client = OpenAI()

# The test question - something with a clear, verifiable answer
TEST_PHRASE = "What is the capital of France?"

OUTPUT_PATH = Path(__file__).parent / "fixtures" / "test_audio.wav"


def generate_test_audio():
    """Generate test audio using TTS and save as WAV."""
    print(f"Generating audio for: '{TEST_PHRASE}'")

    # Generate speech using OpenAI TTS
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=TEST_PHRASE,
        response_format="wav",
    )

    # Save directly
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "wb") as f:
        f.write(response.read())

    print(f"Saved to: {OUTPUT_PATH}")

    # Verify the file
    info = sf.info(OUTPUT_PATH)
    print(f"Duration: {info.duration:.2f}s, Sample rate: {info.samplerate}Hz")


if __name__ == "__main__":
    generate_test_audio()
