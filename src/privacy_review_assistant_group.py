from autogen import AssistantAgent, GroupChat, Agent
from botbuilder.core import TurnContext

from state import AppTurnState
from rag_agents import setup_rag_assistant
from visualizer_agent import setup_visualizer_agent
from threat_model_visualizer import ThreatModelImageVisualizerCapability
from xml_threat_model_reviewer import setup_xml_threat_model_reviewer

USE_XML_ASSISTANT=True

class PrivacyReviewAssistantGroup:
    def __init__(self, llm_config):
        self.llm_config = llm_config
        
    def group_chat_builder(self, context: TurnContext, state: AppTurnState, user_agent: Agent) -> GroupChat:
        rag_assistant = setup_rag_assistant(self.llm_config)
        threat_modeling_assistant = setup_xml_threat_model_reviewer(self.llm_config, context, state) if USE_XML_ASSISTANT else setup_visualizer_agent(context, state, user_agent)
        visualizer_agent = self.setup_visualizer_assistant(context, state, user_agent)
        group = GroupChat(
            agents=[user_agent, rag_assistant, visualizer_agent, threat_modeling_assistant],
            messages=[],
            max_round=100,
            speaker_transitions_type="allowed",
            allowed_or_disallowed_speaker_transitions={
                user_agent: [rag_assistant, visualizer_agent, threat_modeling_assistant],
                rag_assistant: [user_agent],
                visualizer_agent: [user_agent],
                threat_modeling_assistant: [user_agent],
            },
        )
        
        return group

    def setup_visualizer_assistant(self, _context: TurnContext, state: AppTurnState, _user_agent: Agent) -> Agent:        
        visualizer_assistant = AssistantAgent(
            name="Visualizer",
            description="An agent that visualizes the threat model.",
        )
        visualizer_capability = ThreatModelImageVisualizerCapability(state=state)
        visualizer_capability.add_to_agent(visualizer_assistant)
        return visualizer_assistant