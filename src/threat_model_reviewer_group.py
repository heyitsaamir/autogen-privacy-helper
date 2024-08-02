import io
from typing import Union
from PIL import Image
from autogen import AssistantAgent, GroupChat, Agent
from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability

from botbuilder.core import TurnContext
from teams.input_file import InputFile

from state import AppTurnState
from svg_to_png.svg_to_png import convert_svg_to_png

class ThreatModelReviewerGroup:
    def __init__(self, llm_config, threat_model_spec: str = """
1. All nodes (boxes or nodes surrounded by a black border) should be inside a red boundary. Are there any nodes outside the red boundary?
2. It should be clear to tell what each red boundary is.
3. All arrows should be labeled (labels are inside green boxes).
4. All labels for the arrows should have sequential numbers. These numbers indicate the order in which the flow happens. If all arrows do not contains labels, indicate which ones. Otherwise state the flow of data in the order that the arrow point
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

When asking the question, you should format your question in this format:
<QUESTION specRequirement=1>
Your question
</QUESTION>

To ask if nodes are for a valid service or data store in the system, ask one question at a time for each node. Be specific (eg. use the node name in the question).
If you have no questions to ask, say "NO_QUESTIONS" and nothing else.
            """,
            description="A questioner agent that can ask questions based on a threat model picture. It can ask questions about the threat model from the given picture or about the broader system.",
            llm_config={"config_list": [self.llm_config],
                        "timeout": 60, "temperature": 0},
        )
                            
        answerer_agent = MultimodalConversableAgent(
            name="Threat_Model_Image_Answerer",
            system_message="""You are an threat model answerer agent.
Your role is to answer questions based on the threat model picture.
If you do not have a threat model, ask the user to provide one.
You will *never* speculate or infer anything that is not in the threat model picture.
The threat model indicates the flow of data in a bigger system. You do not have any context about the system, but you can answer questions regarding the data flow present in the threat model.
Answer the questions as clearly and concisely as possible.

If you do not understand something from the threat model picture, you may ask a clarifying question. In case of a clarifying question for the user, put your exact question between tags in this format:
<CLARIFYING_QUESTION>
your clarifying question
</CLARIFYING_QUESTION>
            """,
            description="A answerer agent that can exclusively answer questions based on a threat model picture.",
            llm_config={"config_list": [self.llm_config],
                        "timeout": 60, "temperature": 0},
        )
        threat_model_capability = ThreatModelImageVisualizerCapability(state=state, max_width=400)
        threat_model_capability.add_to_agent(answerer_agent)

        answer_evaluator_agent = AssistantAgent(
            name="Overall_spec_evaluator",
            system_message=f"""You are an answer reviewer agent.
Your role is to evaluate the answers given by the Threat_Model_Answerer agent agent.
You are only called if the Questioner agent has no more questions to ask.
Provide details on the quality of the threat model based on the answers given by the answerer agent.
Evaluate the answers based on the following spec criteria:
{self.threat_model_spec}
For each spec criteria that is not met, provide some action items on how to improve the threat model to meet the requirement.
            """,
            description="An answer evaluator agent that can evaluate the answers given by the Threat_Model_Answerer agent.",
            llm_config={"config_list": [self.llm_config],
                        "timeout": 60, "temperature": 0},
        )

        for agent in [questioner_agent, answerer_agent, answer_evaluator_agent]:
            group_chat_agents.append(agent)

        def custom_speaker_selection_func(
            last_speaker: Agent, groupchat: GroupChat
        ) -> Union[Agent, str, list[Agent], None]:
            last_message = groupchat.messages[-1]
            content = last_message.get("content")
            if last_speaker == questioner_agent:
                if content is not None and "NO_QUESTIONS" in content:
                    print("No questions, so moving to answer evaluator")
                    return answer_evaluator_agent
                else:
                    return answerer_agent

            if last_speaker == answerer_agent:
                last_message = groupchat.messages[-1]
                if content is not None and "<CLARIFYING_QUESTION>" in content:
                    print("Clarifying question, so sending question to user")
                    return user_agent
                else:
                    return questioner_agent
                
            # ## If the last speaker is the rag_assistant and it has just provided a tool response,
            # ## then we want to convert that into a user message.
            # if last_speaker == rag_assistant and content and last_message.get("tool_responses"):
            #     return rag_assistant
            
            return 'auto'

        groupchat = GroupChat(
            agents=group_chat_agents,
            messages=[],
            max_round=100,
            speaker_selection_method=custom_speaker_selection_func,
            allowed_or_disallowed_speaker_transitions={
                user_agent: [questioner_agent],
                questioner_agent: [answerer_agent, answer_evaluator_agent],
                answerer_agent: [questioner_agent, user_agent],
                answer_evaluator_agent: [user_agent]
            },
            speaker_transitions_type="allowed"
        )
        return groupchat

class ThreatModelImageVisualizer():
    def __init__(self, state: AppTurnState, max_width=None):
        self.state = state
        self.img = None
        self.extra_details = None
        self.max_width = max_width
    
    def extract_image_from_state(self):
        img = None
        img_details = None
        if self.state.temp.input_files and self.state.temp.input_files[0]:
            if isinstance(self.state.temp.input_files[0], InputFile):
                if self.state.temp.input_files[0].content_type == 'image/jpeg' or self.state.temp.input_files[0].content_type == 'image/png':
                    img = self._get_image(self.state.temp.input_files[0])
                elif self.state.temp.input_files[0].content_type == 'application/vnd.microsoft.teams.file.download.info':
                    # make sure it's a threat model file
                    if self.state.temp.input_files[0].content and isinstance(self.state.temp.input_files[0].content, bytes):
                        if self.state.temp.input_files[0].content.startswith(b"<ThreatModel"):
                            svg_str = self.state.temp.input_files[0].content.decode("utf-8")
                            key_label_tuples = convert_svg_to_png(svg_content=svg_str, out_file="threat_model")
                            img = self._get_image("threat_model.png")
                            if key_label_tuples:
                                for key, label in key_label_tuples:
                                    img_details = img_details + f"\n{key}: {label}" if img_details else f"{key}: {label}"
        self.img = img
        self.extra_details = img_details
    
    def _get_image(self, input_file: Union[InputFile, str]):
        img = Image.open(io.BytesIO(input_file.content) if isinstance(input_file, InputFile) else input_file)
        max_width = self.max_width if self.max_width else img.size[0]
        wpercent = (max_width / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(wpercent)))
        img = img.resize((max_width, hsize))
        return img

class ThreatModelImageVisualizerCapability(AgentCapability, ThreatModelImageVisualizer):
    def __init__(self, **kwargs):
        super().__init__()
        super(AgentCapability, self).__init__(**kwargs)
    
    def add_to_agent(self, agent: MultimodalConversableAgent):
        agent.register_hook("process_all_messages_before_reply", self._add_image_to_messages)
        
    def _add_image_to_messages(self, messages):
        if self.img is None:
            self.extract_image_from_state()
            
        if self.img:
            messages = messages.copy()
            img_message = [{
                "type": "image_url",
                "image_url": {
                    "url": self.img,
                }
            }]
            if self.extra_details:
                img_message.append({
                    "type": "text",
                    "text": f"Here are some helpful labels: {self.extra_details}. Use these to help answer the questions."
                })
            messages.append({"content": img_message, "role": "user"})
        else:
            messages = messages.copy()
            messages.append({"content": "No threat model exists.", "role": "user"})
        return messages