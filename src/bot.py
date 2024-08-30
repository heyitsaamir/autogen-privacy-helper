"""
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the MIT License.

Description: initialize the app and listen for `message` activitys
"""
from typing import Dict
import sys
import traceback
from botbuilder.schema import Activity, ActivityTypes

from botbuilder.core import TurnContext, MemoryStorage, InvokeResponse
from teams import Application, ApplicationOptions, TeamsAdapter
from teams.ai import AIOptions
from teams.ai.actions import ActionTypes, ActionTurnContext
from teams.feedback_loop_data import FeedbackLoopData
from teams.teams_attachment_downloader.teams_attachment_downloader import TeamsAttachmentDownloader
from teams.teams_attachment_downloader.teams_attachment_downloader_options import TeamsAttachmentDownloaderOptions
from autogen_planner import AutoGenPlanner, PredictedSayCommandWithAttachments
# from botbuilder.azure import BlobStorage, BlobStorageSettings
from privacy_review_assistant_group import PrivacyReviewAssistantGroup

from config import Config
from cosmos_memory_storage import CosmosDbPartitionedStorage
from state import AppTurnState
from threat_model_file_utils import get_threat_model_image_file, get_threat_model_xml_file

config = Config()
llm_config = config.build_llm_config()

if config.OPENAI_KEY is None and config.AZURE_OPENAI_KEY is None:
    raise RuntimeError(
        "Unable to build LLM config - please check that OPENAI_KEY or AZURE_OPENAI_KEY is set."
    )

cosmos_config = config.build_cosmos_db_config()
storage = MemoryStorage() if cosmos_config is None else CosmosDbPartitionedStorage(
    cosmos_config
)

threat_model_reviewer_group = PrivacyReviewAssistantGroup(llm_config=llm_config)

adapter = TeamsAdapter(config)
downloader = TeamsAttachmentDownloader(
    TeamsAttachmentDownloaderOptions(config.APP_ID, adapter))

def message_builder(context: TurnContext, state: AppTurnState) -> str:
    if context.activity.text:
        return context.activity.text
    if get_threat_model_xml_file(state) or get_threat_model_image_file(state):
        return "Please evaluate this threat model file"
    return "Hi"

app = Application[AppTurnState](
    ApplicationOptions(
        bot_app_id=config.APP_ID,
        storage=storage,
        adapter=adapter,
        ai=AIOptions(planner=AutoGenPlanner(llm_config=llm_config,
                     build_group_chat=threat_model_reviewer_group.group_chat_builder,
                     message_builder=message_builder)),
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
        response = await context.send_activity(
            Activity(
                type=ActivityTypes.message,
                text=content,
                attachments=context.data.response.attachments,
                channel_data={
                   "feedbackLoopEnabled": True
                },
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
        state.conversation.activity_id = response.id

    return ""


@app.message("/clear")
async def on_login(context: TurnContext, state: AppTurnState):
    await state.conversation.clear(context)
    await context.send_activity("Cleared and ready to analyze next spec")

    return True

@app.message('/useVisual')
async def set_to_visual(context: TurnContext, state: AppTurnState):
    state.conversation.use_xml_evaluator = False
    await state.save(context)
    await context.send_activity("Ready to use visual evaluator")
    return True

@app.message('/useXML')
async def set_to_xml(context: TurnContext, state: AppTurnState):
    state.conversation.use_xml_evaluator = True
    await state.save(context)
    await context.send_activity("Ready to use XML evaluator")
    return True

@app.activity("invoke")
async def feedback_loop(context: TurnContext, state: AppTurnState):
    if context.activity.name != "message/submitAction" or context.activity.value.get("actionName", "") != "feedback" or not context.activity.value:
        return False
    
    activity_value: dict = context.activity.value
    feedback = FeedbackLoopData(
        action_name="feedback",
        action_value=activity_value.get("actionValue", {}),
        reply_to_id=context.activity.reply_to_id,
    )
    
    if not context.activity.channel_id:
        raise ValueError("missing activity.channel_id")
    if not context.activity.conversation:
        raise ValueError("missing activity.conversation")
    if not context.activity.recipient:
        raise ValueError("missing activity.recipient")
    feedback_key = f"feedback_{feedback.reply_to_id}"
    channel_id = context.activity.channel_id
    conversation_id = context.activity.conversation.id
    bot_id = context.activity.recipient.id
    storage_item = feedback.to_dict()
    storage_item["activity_key"] = f"{channel_id}/{bot_id}/conversations/{conversation_id}"
    feedback_details: Dict[str, Dict] = {
        feedback_key: storage_item
    }
    
    await storage.write(feedback_details) # type: ignore
    await context.send_activity(
        Activity(type=ActivityTypes.invoke_response, value=InvokeResponse(status=200, body={}))
    )
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
