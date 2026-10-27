#!/usr/bin/env python3
"""
Step 2: Minimal test script to verify LLM API connectivity.
Reads the API key from environment variables (.env) and executes a single turn.
"""

import os
import sys
from dotenv import load_dotenv

# Load variables from .env
load_dotenv(override=True)

def main():
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    print(f"\n=======================================================")
    print(f"🔍 Step 2: Minimal LLM Connection Test ({provider.upper()})")
    print(f"=======================================================")

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        if not api_key or api_key == "your_gemini_api_key_here":
            print("⚠️  GEMINI_API_KEY is not set in your .env file!")
            print("👉 Get a free key at: https://aistudio.google.com/")
            print("👉 Paste it into .env: GEMINI_API_KEY=AIzaSy...")
            sys.exit(1)

        print(f"Connecting to Gemini Model: {model_name}...")
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            test_prompt = "Hello! Please confirm you can hear me and state in one sentence who you are."
            print(f"Sending prompt: \"{test_prompt}\"\n")
            
            response = client.models.generate_content(
                model=model_name,
                contents=test_prompt
            )
            print("✅ Response received successfully from Gemini:")
            print(f"-------------------------------------------------------")
            print(response.text)
            print(f"-------------------------------------------------------\n")
            print("🎉 API connection confirmed working!\n")

        except Exception as e:
            print(f"❌ Gemini connection failed: {e}")
            sys.exit(1)

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        if not api_key or api_key == "your_openai_api_key_here":
            print("⚠️  OPENAI_API_KEY is not set in your .env file!")
            print("👉 Get a key at: https://platform.openai.com/")
            print("👉 Paste it into .env: OPENAI_API_KEY=sk-...")
            sys.exit(1)

        print(f"Connecting to OpenAI Model: {model_name}...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            test_prompt = "Hello! Please confirm you can hear me and state in one sentence who you are."
            print(f"Sending prompt: \"{test_prompt}\"\n")

            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": test_prompt}],
                temperature=0.7
            )
            reply = response.choices[0].message.content
            print("✅ Response received successfully from OpenAI:")
            print(f"-------------------------------------------------------")
            print(reply)
            print(f"-------------------------------------------------------\n")
            print("🎉 API connection confirmed working!\n")

        except Exception as e:
            print(f"❌ OpenAI connection failed: {e}")
            sys.exit(1)

    else:
        print(f"❌ Unknown LLM_PROVIDER '{provider}'. Must be 'gemini' or 'openai'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
