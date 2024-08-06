import io
from typing import Union
from PIL import Image
from botbuilder.schema import Activity, ActivityTypes, Attachment
from autogen.agentchat import AssistantAgent, Agent
from autogen.agentchat.contrib.multimodal_conversable_agent import ConversableAgent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from autogen.agentchat.contrib.img_utils import pil_to_data_uri

from teams.input_file import InputFile
from botbuilder.core import TurnContext

from svg_to_png.svg_to_png import load_threat_model
from asyncio import ensure_future

from threat_model_visualizer import ThreatModelImageVisualizer

from state import AppTurnState
class ThreatModelDataExtractor(ThreatModelImageVisualizer):
    def __init__(self, state: AppTurnState):
        self.label_names = None
        self.no_boundary_nodes = None
        super(ThreatModelImageVisualizer, self).__init__()
    
    def extract_data_from_state(self):
        if self.state.temp.input_files and self.state.temp.input_files[0]:
            if isinstance(self.state.temp.input_files[0], InputFile):
                if self.state.temp.input_files[0].content_type == 'application/vnd.microsoft.teams.file.download.info':
                    # make sure it's a threat model file
                    if self.state.temp.input_files[0].content and isinstance(self.state.temp.input_files[0].content, bytes):
                        if self.state.temp.input_files[0].content.startswith(b"<ThreatModel"):
                            svg_str = self.state.temp.input_files[0].content.decode("utf-8")
                            threat_model = load_threat_model(svg_content=svg_str)
                            self.label_names = threat_model.get_label_names()
                            self.no_boundary_nodes = threat_model.get_no_threat_boundary_node_names()

class XMLThreatModelImageAddToMessageCapability(AgentCapability, ThreatModelDataExtractor):
    def __init__(self, context: TurnContext, say_when_evaluating: bool, max_width: int, **kwargs):
        self.say_when_evaluating = say_when_evaluating
        self.context = context
        self.max_width = max_width
        
        super().__init__()
        super(AgentCapability, self).__init__(**kwargs)
    
    def add_to_agent(self, agent: ConversableAgent):
        agent.register_hook("process_all_messages_before_reply", self._add_data_to_messages)
        
    def _add_data_to_messages(self, messages):
        if self.img is None:
            self.extract_image_from_state()
            self.extract_data_from_state()
            if self.img:
                jpeg = self.convert_to_jpeg_if_needed(self.img)
                if jpeg:
                    # Unfortunately autogen currently doesn't support async nested chats.
                    # So we need to do this "fire and forget" hack to send the image.
                    ensure_future(self._say_when_evaluating(jpeg))
                self.resize(self.max_width)
        if self.label_names is not None or self.no_boundary_nodes is not None:
            messages = messages.copy()
            content = f"""The nodes with no boundaries are {self.no_boundary_nodes}.
            The list of label names is {self.label_names}."""
            messages.append({"content": content, "role": "user"})
        else:
            messages = messages.copy()
            messages.append({"content": "No threat model exists.", "role": "user"})
        return messages
    
    def resize(self, max_width: int):
        assert self.img is not None, "There is no image to resize!"
        new_img = Image.new(self.img.mode, self.img.size)
        wpercent = (max_width / float(self.img.size[0]))
        hsize = int((float(self.img.size[1]) * float(wpercent)))
        self.img = new_img.resize((max_width, hsize))
    
    async def _say_when_evaluating(self, img: Image.Image):
        if self.say_when_evaluating:
            jpeg = self.convert_to_jpeg_if_needed(img)
            if jpeg:
                await self.context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        text="Here is the threat model we are evaluating",
                        attachments=[Attachment(content_type="image/jpeg", content_url=pil_to_data_uri(jpeg))]
                    )
                )

def setup_xml_threat_model_reviewer(llm_config, context: TurnContext, state: AppTurnState, threat_model_spec: str = """
    1. All nodes (boxes or nodes surrounded by a black border) should be inside a boundary. Are there any nodes not in a boundary?
    2. All labels for the should be numbered sequential numbers. These numbers indicate the order in which the flow happens. If there are numbers in the sequence missing or some labels are not numbered, please say which ones.
    """):
    assistant = AssistantAgent(
        name="Threat_Model_Evaluator",
        description=f"""An agent that manages a group chat for threat modeling validation and evaluation, if the user specifically requests XML validation.
            The agent will do validation based on these rules: {threat_model_spec}. The agent will report in detail which rules are correct and which ones have been broken.""",
        llm_config={"config_list": [llm_config],
                        "timeout": 60, "temperature": 0},
    )

    capability = XMLThreatModelImageAddToMessageCapability(context, True, state=state, max_width=400)
    capability.add_to_agent(assistant)

    return assistant

