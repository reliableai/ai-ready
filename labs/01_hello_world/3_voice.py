"""
Voice In, Voice Out

Record your voice → Whisper transcribes it → LLM responds → TTS speaks the answer.
This shows the full pipeline for voice-based AI interaction.

Run: uv run python labs/01_hello_world/3_voice.py

NOTE: Commented out to prevent accidental API usage. Uncomment to run.
"""

# import tempfile
# from pathlib import Path
#
# import sounddevice as sd
# import soundfile as sf
# from dotenv import load_dotenv
# from openai import OpenAI
#
# load_dotenv()  # Load OPENAI_API_KEY from .env
#
# client = OpenAI()  # Automatically uses OPENAI_API_KEY env var
#
# SAMPLE_RATE = 16000  # Whisper expects 16kHz
# RECORD_SECONDS = 5
#
#
# def record_audio() -> Path:
#     """Record audio from microphone and save to temp file."""
#     print(f"🎤 Recording for {RECORD_SECONDS} seconds... Speak now!")
#
#     audio = sd.rec(
#         int(RECORD_SECONDS * SAMPLE_RATE),
#         samplerate=SAMPLE_RATE,
#         channels=1,
#         dtype="float32",
#     )
#     sd.wait()
#     print("✓ Recording complete")
#
#     temp_file = Path(tempfile.gettempdir()) / "voice_input.wav"
#     sf.write(temp_file, audio, SAMPLE_RATE)
#     return temp_file
#
#
# def transcribe(audio_path: Path) -> str:
#     """Transcribe audio file using Whisper."""
#     print("📝 Transcribing...")
#
#     with open(audio_path, "rb") as f:
#         transcript = client.audio.transcriptions.create(
#             model="whisper-1",
#             file=f,
#         )
#
#     print(f"✓ You said: \"{transcript.text}\"")
#     return transcript.text
#
#
# def get_response(text: str) -> str:
#     """Get LLM response to the transcribed text."""
#     print("🤖 Thinking...")
#
#     response = client.chat.completions.create(
#         model="gpt-4.1-mini",
#         messages=[
#             {"role": "system", "content": "You are a helpful assistant. Keep responses brief and conversational."},
#             {"role": "user", "content": text},
#         ],
#     )
#
#     reply = response.choices[0].message.content
#     print(f"✓ Response: \"{reply}\"")
#     return reply
#
#
# def speak(text: str) -> None:
#     """Convert text to speech and play it."""
#     print("🔊 Speaking...")
#
#     speech_file = Path(tempfile.gettempdir()) / "voice_output.mp3"
#
#     response = client.audio.speech.create(
#         model="tts-1",
#         voice="nova",
#         input=text,
#     )
#
#     response.stream_to_file(speech_file)
#
#     # Play the audio
#     data, samplerate = sf.read(speech_file)
#     sd.play(data, samplerate)
#     sd.wait()
#     print("✓ Done")
#
#
# if __name__ == "__main__":
#     print("\n=== Voice Assistant Demo ===\n")
#
#     # 1. Record
#     audio_path = record_audio()
#
#     # 2. Transcribe (Speech → Text)
#     user_text = transcribe(audio_path)
#
#     # 3. Think (Text → Text)
#     assistant_text = get_response(user_text)
#
#     # 4. Speak (Text → Speech)
#     speak(assistant_text)
#
#     print("\n=== Pipeline complete ===")
