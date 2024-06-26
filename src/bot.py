"""
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the MIT License.

Description: initialize the app and listen for `message` activitys
"""

import os
import sys
import traceback
import base64
import io
import PIL.Image as Image
from typing import Union, Any
from autogen import AssistantAgent, GroupChat, Agent, ConversableAgent, register_function
from botbuilder.schema import Activity, ActivityTypes

from botbuilder.core import TurnContext, MemoryStorage
from teams import Application, ApplicationOptions, TeamsAdapter
from teams.ai import AIOptions
from teams.ai.actions import ActionTypes, ActionTurnContext
from teams.teams_attachment_downloader.teams_attachment_downloader import TeamsAttachmentDownloader
from teams.input_file import InputFile
from teams.teams_attachment_downloader.teams_attachment_downloader_options import TeamsAttachmentDownloaderOptions
from autogen_planner import AutoGenPlanner, PredictedSayCommandWithAttachments
from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent
from botbuilder.azure import BlobStorage, BlobStorageSettings

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

def first(the_iterable, condition=lambda x: True) -> Union[None, Any]:
    for i in the_iterable:
        if condition(i):
            return i

def get_image(bytes: InputFile):
    img = Image.open(io.BytesIO(bytes.content))
    wpercent = (400 / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    img = img.resize((400, hsize))
    return img

def get_image_encoded(bytes: InputFile):
    img = get_image(bytes)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return encoded_image


def build_image_string(image_bytes_as_str: str, image_content_type: str):
    # return f'<img data:{image_content_type};base64,{image_bytes_as_str}>'
    return f'data:{image_content_type};base64,{image_bytes_as_str}'


class ImageReasoningAgent(MultimodalConversableAgent):
    def __init__(self, img: Image.Image | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.img = img

        def add_image_to_messages(messages):
            if self.img:
                messages = messages.copy()
                messages.append({"content": [{
                    "type": "image_url",
                    "image_url": {
                        "url": self.img,
                    }
                }], "role": "user"})
            return messages
        self.hook_lists["process_all_messages_before_reply"].append(
            add_image_to_messages)


threat_model_spec = f"""
1. All nodes (boxes or nodes surrounded by a black border) should be inside a red boundary. Are there any nodes outside the red boundary?
2. It should be clear to tell what each red boundary is.
3. All arrows should be labeled.
4. All labels for the arrows should have sequential numbers. These numbers indicate the order in which the flow happens.  Are you able to understand the sequental flow of the data? Can you describe the data flow from one node to another?
"""


def build_group_chat(context: TurnContext, state: AppTurnState, user_agent: Agent):
    group_chat_agents = [user_agent]
    questioner_agent = AssistantAgent(
        name="Questioner",
        system_message=f"""You are a questioner agent.
Your role is to ask questions for regarding a threat model to evaluate the privacy of a system:
{threat_model_spec}
Ask a single question at a given time.
If you do not have any more questions, say so.

When asking the question, you should include the spec requirement that the question is trying to answer. For example:
<QUESTION specRequirement=1>
Your question
</QUESTION>

If you have no questions to ask, say "NO_QUESTIONS" and nothing else.
        """,
        llm_config={"config_list": [llm_config],
                    "timeout": 60, "temperature": 0},
    )

    img = None
    if state.temp.input_files and state.temp.input_files[0]:
        if isinstance(state.temp.input_files[0][0], InputFile) and (state.temp.input_files[0][0].content_type == 'image/jpeg' or state.temp.input_files[0][0].content_type == 'image/png'):
            img = get_image(state.temp.input_files[0][0])

    answerer_agent = ImageReasoningAgent(
        name="Threat_Model_Answerer",
        system_message=f"""You are an answerer agent.
Your role is to answer questions based on the threat model picture.
If you do not have a threat model, ask the user to provide one.
You will *never* speculate or infer anything that is not in the threat model picture.
Answer the questions as clearly and concisely as possible.

If you do not understand something from the threat model picture, you may ask a clarifying question. In case of a clarifying question for the user, put your exact question between tags like this:
<CLARIFYING_QUESTION>
your clarifying question
</CLARIFYING_QUESTION>
        """,
        llm_config={"config_list": [llm_config],
                    "timeout": 60, "temperature": 0},
        img=img
    )

    answer_evaluator_agent = AssistantAgent(
        name="Overall_spec_evaluator",
        system_message=f"""You are an answer reviewer agent.
        Your role is to evaluate the answers given by the Threat_Model_Answerer agent.
        You are only called if the Questioner agent has no more questions to ask.
        Provide details on the quality of the threat model based on the answers given by the answerer agent.
        Evaluate the answers based on the following spec criteria:
        {threat_model_spec}

        Rate each area on a scale of 1 to 5 as well.
        """,
        llm_config={"config_list": [llm_config],
                    "timeout": 60, "temperature": 0},
    )

    for agent in [questioner_agent, answerer_agent, answer_evaluator_agent]:
        group_chat_agents.append(agent)

    def custom_speaker_selection_func(
        last_speaker: Agent, groupchat: GroupChat
    ) -> Union[Agent, str, None]:
        if last_speaker == questioner_agent:
            last_message = groupchat.messages[-1]
            content = last_message.get("content")
            if content is not None and content.lower() == "no_questions":
                return answer_evaluator_agent
            else:
                return answerer_agent
        return 'auto'

    groupchat = GroupChat(
        agents=group_chat_agents,
        messages=[],
        max_round=100,
        speaker_selection_method=custom_speaker_selection_func,
        allowed_or_disallowed_speaker_transitions={
            user_agent: [questioner_agent],
            questioner_agent: [answerer_agent, answer_evaluator_agent],
            answerer_agent: [user_agent, questioner_agent],
            answer_evaluator_agent: [user_agent]
        },
        speaker_transitions_type="allowed"
    )
    return groupchat


adapter = TeamsAdapter(config)
downloader = TeamsAttachmentDownloader(
    TeamsAttachmentDownloaderOptions(config.APP_ID, adapter))

app = Application[AppTurnState](
    ApplicationOptions(
        bot_app_id=config.APP_ID,
        storage=storage,
        adapter=TeamsAdapter(config),
        ai=AIOptions(planner=AutoGenPlanner(llm_config=llm_config,
                     build_group_chat=build_group_chat)),
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
