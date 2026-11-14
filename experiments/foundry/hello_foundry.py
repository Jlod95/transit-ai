"""Hello Foundry: send one question to a model deployed in a Microsoft Foundry project.

Usage:
    python -m pip install -r experiments/foundry/requirements.txt
    az login
    python experiments/foundry/hello_foundry.py

Reads FOUNDRY_PROJECT_ENDPOINT (the project's endpoint URL) and FOUNDRY_MODEL (the deployment
name in the project's "Deployed models" table) from the environment or the project's .env file.
Signs in with DefaultAzureCredential, so `az login` is all it needs: no API key. Uses the
Responses API through the project's OpenAI client. Not part of the app (src/ is untouched).
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
REQUIRED = ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL")
QUESTION = "In one sentence, what is a GTFS block?"


def read_settings(env):
    """{name: value} for every REQUIRED variable in env; SystemExit naming any that are missing."""
    missing = [name for name in REQUIRED if not (env.get(name) or "").strip()]
    if missing:
        raise SystemExit(
            f"Missing {', '.join(missing)}: add {' and '.join(missing)} to the .env file in "
            f"{PROJECT_ROOT} (the project endpoint URL and the model's deployment name from "
            f"the Foundry portal), then save it."
        )
    return {name: env[name].strip() for name in REQUIRED}


def main():
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    settings = read_settings(os.environ)

    # Imported here so the settings check (and its test) works without the Azure packages.
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=settings["FOUNDRY_PROJECT_ENDPOINT"], credential=credential) as project,
        project.get_openai_client() as client,
    ):
        response = client.responses.create(model=settings["FOUNDRY_MODEL"], input=QUESTION)

    print(f"Q: {QUESTION}")
    print(f"A: {response.output_text}")
    usage = response.usage
    print(f"Tokens: {usage.input_tokens} in, {usage.output_tokens} out, {usage.total_tokens} total "
          f"(model {response.model})")


if __name__ == "__main__":
    sys.exit(main())
