
import io
import PIL.Image as Image
from typing import Union
from autogen import AssistantAgent, GroupChat, Agent

from botbuilder.core import TurnContext
from teams.input_file import InputFile
from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent

from state import AppTurnState

def get_image(bytes: InputFile):
    img = Image.open(io.BytesIO(bytes.content))
    wpercent = (400 / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    img = img.resize((400, hsize))
    return img


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

class ThreatModelReviewerGroup:
    def __init__(self, llm_config, threat_model_spec: str = f"""
1. All nodes (boxes or nodes surrounded by a black border) should be inside a red boundary. Are there any nodes outside the red boundary?
2. It should be clear to tell what each red boundary is.
3. All arrows should be labeled.
4. All labels for the arrows should have sequential numbers. These numbers indicate the order in which the flow happens.  Are you able to understand the sequental flow of the data? Can you describe the data flow from one node to another?
"""):
        self.llm_config = llm_config
        self.threat_model_spec = threat_model_spec
        
    def group_chat_builder(self, _context: TurnContext, state: AppTurnState, user_agent: Agent) -> GroupChat:
        group_chat_agents = [user_agent]
        questioner_agent = AssistantAgent(
            name="Questioner",
            system_message=f"""You are a questioner agent.
    Your role is to ask questions for regarding a threat model to evaluate the privacy of a system:
    {self.threat_model_spec}
    Ask a single question at a given time.
    If you do not have any more questions, say so.

    When asking the question, you should include the spec requirement that the question is trying to answer. For example:
    <QUESTION specRequirement=1>
    Your question
    </QUESTION>

    If you have no questions to ask, say "NO_QUESTIONS" and nothing else.
            """,
            llm_config={"config_list": [self.llm_config],
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
            llm_config={"config_list": [self.llm_config],
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
            {self.threat_model_spec}

            Rate each area on a scale of 1 to 5 as well.
            """,
            llm_config={"config_list": [self.llm_config],
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
                
            if last_speaker == answerer_agent:
                last_message = groupchat.messages[-1]
                if last_message.get("content") == "<CLARIFYING_QUESTION>":
                    return user_agent
                else:
                    return questioner_agent
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