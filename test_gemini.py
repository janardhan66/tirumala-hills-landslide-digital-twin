"""
Google Gemini API Connection & Verification Test
------------------------------------------------
Project: Tirumala Hills Landslide Monitoring and Risk Assessment
SDK: google-genai (Official Google GenAI SDK)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import pytest


def check_gemini_connection():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        pytest.skip("GEMINI_API_KEY is not configured.")
    print("=" * 60)
    print("  Google Gemini API Connection Test")
    print("  Project: Tirumala Hills Landslide Monitoring")
    print("=" * 60)

    # 1. Load environment variables from .env
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"[INFO] Loaded environment variables from: {env_path.name}")
    else:
        load_dotenv()
        print("[INFO] Searching current directory for .env file...")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    # 2. Check API Key presence
    if not api_key:
        print("\n[ERROR] Missing GEMINI_API_KEY!")
        print("-" * 60)
        print("How to resolve:")
        print(f"1. Create a file named '.env' in this directory:")
        print(f"   {Path(__file__).resolve().parent / '.env'}")
        print("2. Add your Google AI Studio API key on a single line:")
        print("   GEMINI_API_KEY=your_actual_gemini_api_key_here")
        print("3. Save the file and re-run: python test_gemini.py")
        print("\nSecurity note: .env is already in .gitignore and will never be committed.")
        print("-" * 60)
        return False

    print("[INFO] GEMINI_API_KEY detected in environment (hidden for security).")

    # 3. Connect using official google-genai SDK
    try:
        from google import genai
        from google.genai import errors
    except ImportError as e:
        print(f"\n[ERROR] Failed to import google-genai: {e}")
        print("Please ensure google-genai is installed: pip install google-genai")
        return False

    try:
        client = genai.Client(api_key=api_key)
        print("[INFO] Initialized Google GenAI Client.")
    except Exception as e:
        print(f"\n[ERROR] Client initialization failed: {e}")
        return False

    # 4. Model selection & testing
    # Check currently available Gemini models for this API key
    candidate_models = [
        os.environ.get("GEMINI_MODEL", "").strip(),
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    try:
        for listed_model in client.models.list():
            model_name = getattr(listed_model, "name", "")
            if isinstance(model_name, str):
                model_name = model_name.split("/")[-1]
            if model_name and "gemini" in model_name.lower():
                candidate_models.append(model_name)
    except Exception as list_err:
        print(f"[WARN] Could not list available models: {list_err}")
    candidate_models = list(dict.fromkeys(
        model for model in candidate_models
        if model and "image" not in model.lower()
    ))
    test_prompt = "Explain landslide monitoring in two simple sentences."

    print(f"\n[INFO] Sending test prompt: \"{test_prompt}\"")

    response = None
    selected_model = None

    for model_name in candidate_models:
        try:
            print(f"[INFO] Attempting connection with model: '{model_name}'...")
            res = client.models.generate_content(
                model=model_name,
                contents=test_prompt
            )
            if res and res.text:
                response = res
                selected_model = model_name
                print(f"[INFO] Successfully generated response with '{model_name}'.")
                break
        except errors.APIError as api_err:
            err_msg = str(api_err)
            if "404" in err_msg or "not found" in err_msg.lower() or "unsupported" in err_msg.lower() or "no longer available" in err_msg.lower():
                print(f"[WARN] Model '{model_name}' not available for this key. Trying alternative...")
                continue
            elif "503" in err_msg or "unavailable" in err_msg.lower() or "high demand" in err_msg.lower():
                print(f"[WARN] Model '{model_name}' high demand/unavailable. Trying alternative...")
                continue
            elif "429" in err_msg or "quota" in err_msg.lower() or "exhausted" in err_msg.lower():
                print(f"\n[ERROR] Quota limit reached (HTTP 429) for model '{model_name}'.")
                print("Explanation: The API key has exceeded its current requests/minute or daily free quota.")
                print("Fix: Check quota at https://aistudio.google.com/ or wait a few minutes before retrying.")
                return False
            elif "400" in err_msg or "403" in err_msg or "api_key_invalid" in err_msg.lower() or "invalid api key" in err_msg.lower():
                print("\n[ERROR] Authentication failed (Invalid API Key).")
                print("Explanation: The provided GEMINI_API_KEY was rejected by Google AI Studio.")
                print("Fix: Generate a fresh key at https://aistudio.google.com/app/apikey and update .env.")
                return False
            else:
                print(f"[WARN] Error with model '{model_name}': {err_msg}. Trying alternative...")
                continue
        except Exception as net_err:
            print(f"\n[ERROR] Network or connection error: {net_err}")
            print("Explanation: Unable to connect to Google Gemini API servers.")
            print("Fix: Check your internet connection or proxy settings.")
            return False

    if not response or not selected_model:
        print("\n[ERROR] Could not generate response with any candidate model.")
        print("Please check your API key permissions and network connectivity.")
        return False

    # 5. Output Results
    print("\n" + "=" * 60)
    print("  GEMINI GENERATED RESPONSE:")
    print("=" * 60)
    print(response.text.strip())
    print("=" * 60)

    print("\n[SUCCESS] Google Gemini API connection verified successfully!")
    print(f"• Model Name Used: {selected_model}")
    print("• Status: Active & Operational")
    print("• Security Check: API key safely loaded from .env without exposure.")
    print("• Next Step: Ready to integrate Question Answering AI Agent into the dashboard.")
    print("=" * 60)
    return True


def test_gemini_connection():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        pytest.skip("GEMINI_API_KEY is not configured.")
    if os.environ.get("GEMINI_LIVE_TEST", "").strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("Live Gemini test is opt-in; set GEMINI_LIVE_TEST=1.")
    assert check_gemini_connection() is True


if __name__ == "__main__":
    success = check_gemini_connection()
    sys.exit(0 if success else 1)
