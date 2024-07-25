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
    AZURE_SEARCH_SERVICE_ENDPOINT = os.environ.get("AZURE_SEARCH_SERVICE_ENDPOINT")
    AZURE_SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME")
    AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
    AZURE_SEMANTIC_SEARCH_CONFIG = os.environ.get("AZURE_SEMANTIC_SEARCH_CONFIG")
    

    def build_llm_config(self):
        if self.OPENAI_KEY:
            autogen_llm_config = {"model": "gpt-4o", "api_key": self.OPENAI_KEY}
        elif self.AZURE_OPENAI_KEY and self.AZURE_OPENAI_ENDPOINT:
            autogen_llm_config = {
                "model": "my-gpt-4-deployment",
                "api_version": "2024-02-01",
                "api_type": "azure",
                "api_key": self.AZURE_OPENAI_KEY,
                "base_url": self.AZURE_OPENAI_ENDPOINT,
            }
        else:
            return None
        return autogen_llm_config