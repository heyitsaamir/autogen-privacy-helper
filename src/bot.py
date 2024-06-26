"""
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the MIT License.

Description: initialize the app and listen for `message` activitys
"""

import os
import sys
import traceback
from botbuilder.schema import Activity, ActivityTypes

from botbuilder.core import TurnContext
from teams import Application, ApplicationOptions, TeamsAdapter
from teams.ai import AIOptions
from teams.ai.actions import ActionTypes, ActionTurnContext
from teams.teams_attachment_downloader.teams_attachment_downloader import TeamsAttachmentDownloader
from teams.teams_attachment_downloader.teams_attachment_downloader_options import TeamsAttachmentDownloaderOptions
from autogen_planner import AutoGenPlanner, PredictedSayCommandWithAttachments
from botbuilder.azure import BlobStorage, BlobStorageSettings
from threat_model_reviewer_group import ThreatModelReviewerGroup

from config import Config
from state import AppTurnState

config = Config()

if config.OPENAI_KEY is None and config.AZURE_OPENAI_KEY is None:
    raise RuntimeError(
        "Missing environment variables - please check that OPENAI_KEY or AZURE_OPENAI_KEY is set."
    )


llm_config = {"model": "gpt-4-turbo", "api_key": os.environ["OPENAI_KEY"]}

# storage = MemoryStorage()
blob_settings = BlobStorageSettings(
    connection_string=config.BLOB_CONNECTION_STRING,
    container_name=config.BLOB_CONTAINER_NAME
)
storage = BlobStorage(blob_settings)

threat_model_reviewer_group = ThreatModelReviewerGroup(llm_config=llm_config)

adapter = TeamsAdapter(config)
downloader = TeamsAttachmentDownloader(
    TeamsAttachmentDownloaderOptions(config.APP_ID, adapter))

app = Application[AppTurnState](
    ApplicationOptions(
        bot_app_id=config.APP_ID,
        storage=storage,
        adapter=TeamsAdapter(config),
        ai=AIOptions(planner=AutoGenPlanner(llm_config=llm_config,
                     build_group_chat=threat_model_reviewer_group.group_chat_builder)),
        file_downloaders=[downloader],
    ),
)


@app.ai.action(ActionTypes.SAY_COMMAND)
async def say_command(context: ActionTurnContext[PredictedSayCommandWithAttachments], state: AppTurnState):
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
