import io
from typing import Union
from PIL import Image
from botbuilder.schema import Activity, ActivityTypes, Attachment
from autogen.agentchat import AssistantAgent, Agent
from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from autogen.agentchat.contrib.img_utils import pil_to_data_uri

from teams.input_file import InputFile
from botbuilder.core import TurnContext

from state import AppTurnState
from svg_to_png.svg_to_png import convert_svg_to_png
from asyncio import ensure_future

class ThreatModelImageVisualizer():
    def __init__(self, state: AppTurnState):
        self.state = state
        self.img = None
        self.extra_details = None
    
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
        return img
    
    def convert_to_jpeg_if_needed(self, image: Image.Image):
        if image.mode != "RGB":
            new_image = Image.new("RGBA", image.size, "WHITE") # Create a white rgba background
            jpeg_img = Image.alpha_composite(new_image, image)
            return jpeg_img
        return
    

    
class ThreatModelImageVisualizerCapability(AgentCapability, ThreatModelImageVisualizer):
    def __init__(self, state: AppTurnState):
        super().__init__()
        super(AgentCapability, self).__init__(state)
    
    def add_to_agent(self, agent: AssistantAgent):
        agent.register_reply([Agent, None], self._reply_with_image, remove_other_reply_funcs=True)
        
    def _reply_with_image(self, self2, messages, sender, config):
        if self.img is None:
            self.extract_image_from_state()
            if self.img:
                jpeg = self.convert_to_jpeg_if_needed(self.img)
                if jpeg:
                    self.img = jpeg
            
        if self.img:
            return [True, self._convert_image_to_data_uri(self.img)]
        else:
            return [True, "No threat model available"]
        
    def _convert_image_to_data_uri(self, image: Image.Image):
        return pil_to_data_uri(image)

class ThreatModelImageAddToMessageCapability(AgentCapability, ThreatModelImageVisualizer):
    def __init__(self, context: TurnContext, say_when_evaluating: bool, max_width: int, **kwargs):
        self.say_when_evaluating = say_when_evaluating
        self.context = context
        self.max_width = max_width
        
        super().__init__()
        super(AgentCapability, self).__init__(**kwargs)
    
    def add_to_agent(self, agent: MultimodalConversableAgent):
        agent.register_hook("process_all_messages_before_reply", self._add_image_to_messages)
        
    def _add_image_to_messages(self, messages):
        if self.img is None:
            self.extract_image_from_state()
            if self.img:
                jpeg = self.convert_to_jpeg_if_needed(self.img)
                if jpeg:
                    # Unfortunately autogen currently doesn't support async nested chats.
                    # So we need to do this "fire and forget" hack to send the image.
                    ensure_future(self._say_when_evaluating(jpeg))
                self.resize(self.max_width)
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