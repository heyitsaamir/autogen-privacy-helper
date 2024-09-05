import os
from PIL import Image
from botbuilder.schema import Activity, ActivityTypes, Attachment
from autogen.agentchat import AssistantAgent
from autogen.agentchat.contrib.multimodal_conversable_agent import ConversableAgent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from autogen.agentchat.contrib.img_utils import pil_to_data_uri

from botbuilder.core import TurnContext

from Spec import load_specs_from_json
from svg_to_png.svg_to_png import load_threat_model
from asyncio import ensure_future

from threat_model_file_utils import get_threat_model_xml_file
from threat_model_visualizer import ThreatModelImageVisualizer

from state import AppTurnState


class ThreatModelDataExtractor(ThreatModelImageVisualizer):
    def __init__(self, context: TurnContext, state: AppTurnState):
        self.label_names = None
        self.no_boundary_nodes = None
        self.state = state
        super().__init__(context=context, state=state)

    def extract_data_from_state(self):
        xml_file = get_threat_model_xml_file(self.state)
        if xml_file:
            svg_str = xml_file.content.decode("utf-8")
            threat_model = load_threat_model(svg_content=svg_str)
            self.label_names = threat_model.get_label_names()
            self.node_data = threat_model.get_node_data()
            self.boundary_names = threat_model.get_boundary_names()
            self.node_label_pair_data = threat_model.get_node_label_pair_data()


class XMLThreatModelImageAddToMessageCapability(
    AgentCapability, ThreatModelDataExtractor
):
    def __init__(
        self,
        context: TurnContext,
        say_when_evaluating: bool,
        max_width: int,
        set_message_to_second_last=False,
        **kwargs,
    ):
        self.say_when_evaluating = say_when_evaluating
        self.context = context
        self.max_width = max_width
        self.img = None
        self.set_message_to_second_last = set_message_to_second_last

        super().__init__()
        super(AgentCapability, self).__init__(context=context, **kwargs)

    def add_to_agent(self, agent: ConversableAgent):
        agent.register_hook(
            "process_all_messages_before_reply", self._add_data_to_messages
        )

    def _add_data_to_messages(self, messages):
        if self.img is None:
            self.extract_image_from_state(build_for_ai_context=False)
            self.extract_data_from_state()
            if self.img:
                jpeg = self.convert_to_jpeg_if_needed(self.img)
                if jpeg:
                    # Unfortunately autogen currently doesn't support async nested chats.
                    # So we need to do this "fire and forget" hack to send the image.
                    ensure_future(self._say_when_evaluating(jpeg))
                self.resize(self.max_width)
        if self.label_names is not None or self.node_data is not None:
            messages = messages.copy()
            content = f"""The file details for the file you need to validate are: 
--------
1. The data for the nodes is: {self.node_data}.
--------
2. The list of label names is {self.label_names}.
--------
3. The list of nodes with labels between them is {self.node_label_pair_data}.
--------
4. The list of boundary names is {self.boundary_names}."""
            # make this the second last message
            messages.insert(
                -1 if self.set_message_to_second_last else len(messages),
                {"content": content, "role": "user"},
            )
            # messages.append({"content": content, "role": "user"})
        else:
            messages = messages.copy()
            messages.append({"content": "No threat model exists.", "role": "user"})
        return messages

    def resize(self, max_width: int):
        assert self.img is not None, "There is no image to resize!"
        new_img = Image.new(self.img.mode, self.img.size)
        wpercent = max_width / float(self.img.size[0])
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
                        attachments=[
                            Attachment(
                                content_type="image/jpeg",
                                content_url=pil_to_data_uri(jpeg),
                            )
                        ],
                    )
                )

folder = os.path.dirname(os.path.abspath(__file__))
specs = load_specs_from_json(f"{folder}/specs.json")


def setup_xml_threat_model_reviewer(
    llm_config,
    context: TurnContext,
    state: AppTurnState,
    threat_model_spec: str = """
1. All nodes should be inside a boundary. Are there any nodes not in a boundary? To determine if a node is within a boundary in the node data for a node, has_boundary should be true. Do not tell the user of the has_boundary flag, however, just whether a node is not in a boundary.
2. All labels should be numbered with sequential numbers. The labels themselves may not be in sequential order, but all numbers in the sequence must be there. For example, if you
the labels are first "1. FlowA" and second "3. FlowB" and third, "2. FlowC", this is valid, because all numbers between 1 and 3 are there, but if it were "1. FlowA" and second 
"4. FlowB" and third, "2. FlowC" then this would be invalid, because 3 is missing.
3. All nodes and labels should be tagged with [NEW] or [EXISTING] to denote which part of the DFD is to be reviewed.
4. Validate a request and response for each node and that there is a label. If in the list of nodes with labels between them for two nodes either hasNode2ToNode1Curve or hasNode1ToNode2Curve are not true, say that there aren't curves in both directions between these nodes. Do not use strings like hasNode2ToNode1Curve in the response.
5. Each storage node can have a tag like 30D that represents its retention. If no storage nodes have this tag issue a warning but this should not be a validation failure. If there is a tag that appears like it's a duration it should be in compact duration format. Only for [NEW] nodes
6. Each label should have a string representing the type of data it passes. Therefore it should include one of the following: AC, CC, EUII, OII, SM PND, EUPI, SD, FB, AD PPD MSD.
7. There should not be any JSON in any of the labels. Only tags should be in the labels.
    """,
):
    # threat_model_spec = ''
    # for spec in specs:
    #     threat_model_spec += f"#{spec.id}. {spec.spec}\n{spec.instructions_to_solve}\n\n"

    assistant = AssistantAgent(
        name="Threat_Model_Evaluator",
        description="You are a threat model evaluator that evaluates threat models based on given data and rules.",
        system_message=f"""You are a helpful threat model file evaluator that evaluates whether the data is correct from given rules
            using only the data given to you.
            These are the rules you need to do evaluation based on: {threat_model_spec}. Your role is to report back what are the 
            issues with the data given the rules. When responding, do not respond referring to the rules by number, but instead 
            describe the rule to the user. Please respond in a clear bullet pointed answer on what the issues are with the data.
            Certainly, never respond with code that the user should try to execute.
            Please group the responses in three groups:
            1. **Needs to be addressed** for validation failures
            2. **Green** for items that are done correctly
            3. **Warnings** for items that are not incorrect but are warnings
                                                    
            For any node that has newline characters like \n or \r please filter out these characters in your response. Also, filter out any JSON.""",
        llm_config={"config_list": [llm_config], "timeout": 60, "temperature": 0},
    )

    capability = XMLThreatModelImageAddToMessageCapability(
        context, True, state=state, max_width=400
    )
    capability.add_to_agent(assistant)

    return assistant
