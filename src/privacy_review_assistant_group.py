from autogen import AssistantAgent, GroupChat, GroupChatManager, Agent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from autogen.agentchat.contrib.img_utils import pil_to_data_uri
from botbuilder.core import TurnContext
from PIL import Image

from state import AppTurnState
from rag_agents import setup_rag_assistant
from threat_model_reviewer_group import ThreatModelReviewerGroup, ThreatModelImageVisualizer

class PrivacyReviewAssistantGroup:
    def __init__(self, llm_config):
        self.llm_config = llm_config
        
    def group_chat_builder(self, context: TurnContext, state: AppTurnState, user_agent: Agent) -> GroupChat:
        rag_assistant = setup_rag_assistant(self.llm_config)
        threat_modeling_assistant = self.setup_threat_modeling_assistant(context, state, user_agent)
        visualizer_agent = self.setup_visualizer_assistant(context, state, user_agent)
        group = GroupChat(
            agents=[user_agent, rag_assistant, threat_modeling_assistant, visualizer_agent],
            messages=[],
            max_round=100,
            speaker_transitions_type="allowed",
            allowed_or_disallowed_speaker_transitions={
                user_agent: [rag_assistant, threat_modeling_assistant, visualizer_agent],
                rag_assistant: [user_agent],
                threat_modeling_assistant: [user_agent],
                visualizer_agent: [user_agent],
            },
        )
        
        return group
    
    def setup_threat_modeling_assistant(self, context: TurnContext, state: AppTurnState, user_agent: Agent) -> Agent:
        def terminate_chat(message):
            message_sender_name = message.get("name", "")
            return message_sender_name != user_agent.name
        assistant = AssistantAgent(
            name="Threat_Model_Evaluator",
            description="An agent that manages a group chat for threat modeling validation and evaluation.",
            is_termination_msg=terminate_chat
        )
        
        threat_modeling_group = ThreatModelReviewerGroup(llm_config=self.llm_config).group_chat_builder(context, state, assistant)
        threat_modeling_group_manager = GroupChatManager(
            groupchat=threat_modeling_group,
            llm_config=self.llm_config,
        )
        def trigger(sender):
            return sender not in [assistant]
        assistant.register_nested_chats([
            {
                "recipient": threat_modeling_group_manager,
                "sender": assistant,
                "summary_method": "last_msg",
                "max_turns": 1,
            },
        ], trigger=trigger)
        return assistant

    def setup_visualizer_assistant(self, _context: TurnContext, state: AppTurnState, _user_agent: Agent) -> Agent:        
        visualizer_assistant = AssistantAgent(
            name="Visualizer",
            description="An agent that visualizes the threat model.",
        )
        visualizer_capability = ThreatModelImageVisualizerCapability(state=state)
        visualizer_capability.add_to_agent(visualizer_assistant)
        return visualizer_assistant
    
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
                self._convert_to_jpeg_if_needed(self.img)
            
        if self.img:
            return [True, self._convert_image_to_data_uri(self.img)]
        else:
            return [True, "No threat model available"]
        
    def _convert_to_jpeg_if_needed(self, image: Image.Image):
        if image.mode != "RGB":
            new_image = Image.new("RGBA", image.size, "WHITE") # Create a white rgba background
            jpeg_img = Image.alpha_composite(new_image, image)
            self.img = jpeg_img
        return
        
    def _convert_image_to_data_uri(self, image: Image.Image):
        return pil_to_data_uri(image)