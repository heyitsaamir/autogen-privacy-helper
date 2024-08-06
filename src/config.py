"""
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the MIT License.
"""

import os

from dotenv import load_dotenv

load_dotenv()

class Config:
    """Bot Configuration"""

    PORT = 3978
    APP_ID = os.environ["BOT_ID"]
    APP_PASSWORD = os.environ.get("BOT_PASSWORD", os.environ.get("SECRET_BOT_PASSWORD", "BAD_PASSWORD"))
    OPENAI_KEY = os.environ.get("OPENAI_KEY", "")
    AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
    AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    AZURE_SEARCH_SERVICE_ENDPOINT = os.environ.get("AZURE_SEARCH_SERVICE_ENDPOINT", "")
    AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
    AZURE_MANAGED_IDENTITY_CLIENT_ID = os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID")
    AZURE_LLM_MODEL = os.environ.get("AZURE_LLM_MODEL")
    AZURE_LLM_BASE_URL = os.environ.get("AZURE_LLM_BASE_URL")

    def build_llm_config(self):
        if self.OPENAI_KEY:
            autogen_llm_config = {"model": "gpt-4o-mini", "api_key": self.OPENAI_KEY}
        elif self.AZURE_OPENAI_KEY and self.AZURE_OPENAI_ENDPOINT:
            autogen_llm_config = {
                "model": "my-gpt-4-deployment",
                "api_version": "2024-02-01",
                "api_type": "azure",
                "api_key": self.AZURE_OPENAI_KEY,
                "base_url": self.AZURE_OPENAI_ENDPOINT,
            }
        elif self.AZURE_MANAGED_IDENTITY_CLIENT_ID and self.AZURE_LLM_MODEL and self.AZURE_LLM_BASE_URL:
            import azure.identity
            autogen_llm_config = {
                "model": self.AZURE_LLM_MODEL,
                "base_url": self.AZURE_LLM_BASE_URL,
                "api_type": "azure",
                "api_version": "2023-05-15",
                "cache_seed": None,
                "azure_ad_token_provider": azure.identity.get_bearer_token_provider(
                    azure.identity.DefaultAzureCredential(
                        managed_identity_client_id = self.AZURE_MANAGED_IDENTITY_CLIENT_ID,
                        exclude_environment_credential = True
                    ), "https://cognitiveservices.azure.com/.default"
                )
            }
        else:
            raise ValueError("Neither OPENAI_KEY nor AZURE_OPENAI_KEY nor azure managed identity (AZURE_MANAGED_IDENTITY_CLIENT_ID, AZURE_LLM_MODEL, AZURE_LLM_BASE_URL) environment variables are set.")
        return autogen_llm_config