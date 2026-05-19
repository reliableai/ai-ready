"""
Image Generation with DALL-E

Text in, image out. Describe what you want, get a picture.
The image URL is temporary - download it if you want to keep it.

Run: uv run python labs/01_hello_world/4_image.py

NOTE: Commented out to prevent accidental API usage (~$0.04 per call). Uncomment to run.
"""

# import time
# import webbrowser
#
# from dotenv import load_dotenv
# from openai import OpenAI
#
# load_dotenv()  # Load OPENAI_API_KEY from .env
#
# client = OpenAI()  # Automatically uses OPENAI_API_KEY env var
#
# PROMPT = "A robot teaching a classroom of humans about artificial intelligence, digital art style"
#
# print(f"🎨 Generating image...")
# print(f"   Prompt: \"{PROMPT}\"\n")
#
# start = time.time()
#
# response = client.images.generate(
#     model="dall-e-3",
#     prompt=PROMPT,
#     size="1024x1024",
#     quality="standard",
#     n=1,
# )
#
# elapsed = time.time() - start
#
# image_url = response.data[0].url
# revised_prompt = response.data[0].revised_prompt
#
# print(f"✓ Image generated in {elapsed:.1f}s\n")
# print(f"📝 DALL-E revised your prompt to:")
# print(f"   \"{revised_prompt}\"\n")
# print(f"🔗 Image URL (temporary, ~1 hour):")
# print(f"   {image_url}\n")
#
# # Open in browser
# print("Opening in browser...")
# webbrowser.open(image_url)
