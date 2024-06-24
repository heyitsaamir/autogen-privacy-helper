"""
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the MIT License.

Description: initialize the app and listen for `message` activitys
"""

import os, sys, traceback, base64, io, PIL.Image as Image
from typing import Union, Any
from autogen import AssistantAgent, GroupChat, Agent
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

from config import Config
from state import AppTurnState

config = Config()

if config.OPENAI_KEY is None and config.AZURE_OPENAI_KEY is None:
    raise RuntimeError(
        "Missing environment variables - please check that OPENAI_KEY or AZURE_OPENAI_KEY is set."
    )


llm_config = {"model": "gpt-4o", "api_key": os.environ["OPENAI_KEY"]}
# downloads the file and returns the contents in a string


def download_file_and_return_contents(download_url):
    import requests
    response = requests.get(download_url)
    return response.text


storage = MemoryStorage()


def first(the_iterable, condition=lambda x: True) -> Union[None, Any]:
    for i in the_iterable:
        if condition(i):
            return i


def get_image(bytes: InputFile):
    img = Image.open(io.BytesIO(bytes.content))
    wpercent = (500 / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    img = img.resize((500, hsize), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return encoded_image


def build_image_string(image_bytes_as_str: str, image_content_type: str):
    return f'<img data:{image_content_type};base64,{image_bytes_as_str}>'


def message_builder(context: TurnContext, state: AppTurnState) -> str:
    image_str = None
    if state.temp.input_files and state.templ.input_files[0]:
        if isinstance(state.temp.input_files[0][0], InputFile) and (state.temp.input_files[0][0].content_type == 'image/jpeg' or state.temp.input_files[0][0].content_type == 'image/png'):
            image_str = build_image_string(get_image(
                state.temp.input_files[0][0]), state.temp.input_files[0][0].content_type)
    return f"""{context.activity.text}
{f'Here is the threat model image: {image_str}' if image_str else 'I currently do not have a threat model image. Ask me to provide you one.'}
        """


threat_model_spec = f"""
1. All nodes (boxes in suddounded by a black border) should be inside a red boundary.
2. It should be clear to tell what each red boundary is.
3. All arrows should be labeled.
4. All labels for the arrows should have numbers. These numbers indicate the order in which the flow happens.
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
        <question> (for spec requirement 1)

        If you have no questions to ask, say "NO_QUESTIONS" and nothing else.
        """,
        llm_config={"config_list": [llm_config],
                    "timeout": 60, "temperature": 0},
    )
    answerer_agent = MultimodalConversableAgent(
        name="Threat_Model_Answerer",
        system_message=f"""You are an answerer agent.
        Your role is to answer questions based on the threat model picture.
        If you do not have a diagram, ask the user to provide one.
        If you do not understand something from the diagram, you may ask a clarifying question.
        Answer the questions as clearly and concisely as possible.

        DO NOT under any circumstance answer a question that is not based on threat model picture.
        """,
        llm_config={"config_list": [llm_config],
                    "timeout": 60, "temperature": 0},
    )
    # if spec_url:
    #     d_retrieve_content = answerer_agent.register_for_llm(
    #         description="Retrieve the contents of the product spec", api_style="function"
    #     )(read_spec)
    #     answerer_agent.register_for_execution()(d_retrieve_content)

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
                     build_group_chat=build_group_chat, messageBuilder=message_builder)),
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
