"""
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the MIT License.
"""

import os

from dotenv import load_dotenv

from cosmos_memory_storage import CosmosDbPartitionedConfig
load_dotenv()

class Config:
    """Bot Configuration"""

    PORT = 3978
    APP_ID = os.environ["BOT_ID"]
    APP_TYPE = os.environ.get("APP_TYPE", "MultiTenant")
    APP_TENANTID = os.environ.get("TENANT_ID", None)
    APP_PASSWORD = os.environ.get("BOT_PASSWORD", os.environ.get("SECRET_BOT_PASSWORD", "BAD_PASSWORD"))
    OPENAI_KEY = os.environ.get("OPENAI_KEY", "")
    AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
    AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    AZURE_SEARCH_SERVICE_ENDPOINT = os.environ.get("AZURE_SEARCH_SERVICE_ENDPOINT", "")
    AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
    AZURE_LLM_MANAGED_IDENTITY_CLIENT_ID = os.environ.get("AZURE_LLM_MANAGED_IDENTITY_CLIENT_ID")
    AZURE_LLM_MODEL = os.environ.get("AZURE_LLM_MODEL")
    AZURE_LLM_BASE_URL = os.environ.get("AZURE_LLM_BASE_URL")
    COSMOS_DB_URI=os.environ.get("COSMOS_DB_URI")
    COSMOS_DB_DATABASE_ID=os.environ.get("COSMOS_DB_DATABASE_ID")
    COSMOS_DB_CONTAINER_ID=os.environ.get("COSMOS_DB_CONTAINER_ID")
    AZURE_MANAGED_IDENTITY_CLIENT_ID=os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID")
    COSMOS_DB_CONNECTION_STRING=os.environ.get("COSMOS_DB_CONNECTION_STRING")
    ENABLE_CHAT_HISTORY_SENDING=os.environ.get("ENABLE_CHAT_HISTORY_SENDING", "false").lower() == "true"

    def build_llm_config(self):
        if self.OPENAI_KEY:
            print("Using OpenAI API")
            autogen_llm_config = {"model": "gpt-4o-mini", "api_key": self.OPENAI_KEY}
        elif self.AZURE_OPENAI_KEY and self.AZURE_OPENAI_ENDPOINT:
            print("Using Azure OpenAI API")
            autogen_llm_config = {
                "model": "my-gpt-4-deployment",
                "api_version": "2024-02-01",
                "api_type": "azure",
                "api_key": self.AZURE_OPENAI_KEY,
                "base_url": self.AZURE_OPENAI_ENDPOINT,
            }
        elif self.AZURE_LLM_MANAGED_IDENTITY_CLIENT_ID and self.AZURE_LLM_MODEL and self.AZURE_LLM_BASE_URL:
            print("Using Azure OpenAI API with managed identity")
            import azure.identity
            autogen_llm_config = {
                "model": self.AZURE_LLM_MODEL,
                "base_url": self.AZURE_LLM_BASE_URL,
                "api_type": "azure",
                "api_version": "2023-05-15",
                "cache_seed": None,
                "azure_ad_token_provider": azure.identity.get_bearer_token_provider(
                    azure.identity.DefaultAzureCredential(
                        managed_identity_client_id = self.AZURE_LLM_MANAGED_IDENTITY_CLIENT_ID,
                        exclude_environment_credential = True
                    ), "https://cognitiveservices.azure.com/.default"
                )
            }
        else:
            raise ValueError("Neither OPENAI_KEY nor AZURE_OPENAI_KEY nor azure managed identity (AZURE_LLM_MANAGED_IDENTITY_CLIENT_ID, AZURE_LLM_MODEL, AZURE_LLM_BASE_URL) environment variables are set.")
        return autogen_llm_config
    
    def build_cosmos_db_config(self):
        if self.COSMOS_DB_URI is None or self.COSMOS_DB_DATABASE_ID is None or self.COSMOS_DB_CONTAINER_ID is None or (self.AZURE_MANAGED_IDENTITY_CLIENT_ID is None and self.COSMOS_DB_CONNECTION_STRING is None):
            return None
        
        if self.COSMOS_DB_CONNECTION_STRING is not None:
            print("Using Cosmos DB with connection string")
            return CosmosDbPartitionedConfig(
                self.COSMOS_DB_URI,
                credential=self.COSMOS_DB_CONNECTION_STRING,
                database_id=self.COSMOS_DB_DATABASE_ID,
                container_id=self.COSMOS_DB_CONTAINER_ID,
            )
        
        import azure.identity
        print("Using Cosmos DB with managed identity")
        return CosmosDbPartitionedConfig(
            self.COSMOS_DB_URI,
            credential=azure.identity.DefaultAzureCredential(
                managed_identity_client_id=self.AZURE_MANAGED_IDENTITY_CLIENT_ID,
                exclude_environment_credential = True
            ),
            database_id=self.COSMOS_DB_DATABASE_ID,
            container_id=self.COSMOS_DB_CONTAINER_ID,
        )