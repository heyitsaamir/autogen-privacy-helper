"""
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the MIT License.

Description: initialize the app and listen for `message` activitys
"""

import os
import sys
import traceback
from botbuilder.schema import Activity, ActivityTypes

from botbuilder.core import TurnContext, MemoryStorage
from teams import Application, ApplicationOptions, TeamsAdapter
from teams.ai import AIOptions
from teams.ai.actions import ActionTypes, ActionTurnContext
from teams.teams_attachment_downloader.teams_attachment_downloader import TeamsAttachmentDownloader
from teams.teams_attachment_downloader.teams_attachment_downloader_options import TeamsAttachmentDownloaderOptions
from autogen_planner import AutoGenPlanner, PredictedSayCommandWithAttachments
# from botbuilder.azure import BlobStorage, BlobStorageSettings
from threat_model_helper_group import ThreatModelHelperGroup

from config import Config
from state import AppTurnState

import azure.identity

config = Config()
def build_llm_config():
    if "OPENAI_KEY" in os.environ:
        config = {"model": "gpt-4o-mini", "api_key": os.environ["OPENAI_KEY"]}
    elif "AZURE_OPENAI_KEY" in os.environ and "AZURE_OPENAI_ENDPOINT" in os.environ:
        config = {
            "model": "my-gpt-4-deployment",
            "api_version": "2024-02-01",
            "api_type": "azure",
            "api_key": os.environ['AZURE_OPENAI_API_KEY'],
            "base_url": os.environ['AZURE_OPENAI_ENDPOINT'],
        }
    elif "AZURE_MANAGED_IDENTITY_CLIENT_ID" in os.environ and "AZURE_LLM_MODEL" in os.environ and "AZURE_LLM_BASE_URL" in os.environ:
        config = {
            "model": os.environ["AZURE_LLM_MODEL"],
            "base_url": os.environ["AZURE_LLM_BASE_URL"],
            "api_type": "azure",
            "api_version": "2023-05-15",
            "cache_seed": None,
            "azure_ad_token_provider": azure.identity.get_bearer_token_provider(
                azure.identity.DefaultAzureCredential(
                    managed_identity_client_id = os.environ["AZURE_MANAGED_IDENTITY_CLIENT_ID"],
                    exclude_environment_credential = True
                ), "https://cognitiveservices.azure.com/.default"
            )
        }
    else:
        raise ValueError("Neither OPENAI_KEY nor AZURE_OPENAI_KEY nor azure managed identity (AZURE_MANAGED_IDENTITY_CLIENT_ID, AZURE_LLM_MODEL, AZURE_LLM_BASE_URL) environment variables are set.")
    return config

llm_config = config.build_llm_config()

if config.OPENAI_KEY is None and config.AZURE_OPENAI_KEY is None:
    raise RuntimeError(
        "Unable to build LLM config - please check that OPENAI_KEY or AZURE_OPENAI_KEY is set."
    )

storage = MemoryStorage()

threat_model_reviewer_group = ThreatModelHelperGroup(llm_config=llm_config)

adapter = TeamsAdapter(config)
downloader = TeamsAttachmentDownloader(
    TeamsAttachmentDownloaderOptions(config.APP_ID, adapter))

app = Application[AppTurnState](
    ApplicationOptions(
        bot_app_id=config.APP_ID,
        storage=storage,
        adapter=adapter,
        ai=AIOptions(planner=AutoGenPlanner(llm_config=llm_config,
                     build_group_chat=threat_model_reviewer_group.group_chat_builder)),
        file_downloaders=[downloader],
    ),
)


@app.ai.action(ActionTypes.SAY_COMMAND)
async def say_command(context: ActionTurnContext[PredictedSayCommandWithAttachments], _state: AppTurnState):
    content = (
        context.data.response.content
        if context.data.response and context.data.response.content
        else ""
    )

    if content:
        await context.send_activity(
            Activity(
                type=ActivityTypes.message,
                text=content,
                attachments=context.data.response.attachments,
                entities=[
                    {
                        "type": "https://schema.org/Message",
                        "@type": "Message",
                        "@context": "https://schema.org",
                        "@id": "",
                        "additionalType": ["AIGeneratedContent"],
                    }
                ],
            )
        )

    return ""


@app.message("/clear")
async def on_login(context: TurnContext, state: AppTurnState):
    await state.conversation.clear(context)
    await context.send_activity("Cleared and ready to analyze next spec")

    return True


@app.turn_state_factory
async def turn_state_factory(context: TurnContext):
    return await AppTurnState.load(context, storage)


@app.error
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Send a message to the user
    await context.send_activity("The bot encountered an error or bug.")
