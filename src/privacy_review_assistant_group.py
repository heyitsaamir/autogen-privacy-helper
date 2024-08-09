from autogen import AssistantAgent, GroupChat, GroupChatManager, Agent
from botbuilder.core import TurnContext

from state import AppTurnState
from rag_agents import setup_rag_assistant
from threat_model_reviewer_group import ThreatModelReviewerGroup
from threat_model_visualizer import ThreatModelImageVisualizerCapability
from xml_threat_model_reviewer import setup_xml_threat_model_reviewer

class PrivacyReviewAssistantGroup:
    def __init__(self, llm_config):
        self.llm_config = llm_config
        
    def group_chat_builder(self, context: TurnContext, state: AppTurnState, user_agent: Agent) -> GroupChat:
        rag_assistant = setup_rag_assistant(self.llm_config)
        threat_modeling_assistant = self.setup_threat_modeling_assistant(context, state, user_agent)
        visualizer_agent = self.setup_visualizer_assistant(context, state, user_agent)
        xml_threat_model_reviewer = setup_xml_threat_model_reviewer(self.llm_config, context, state)
        group = GroupChat(
            agents=[user_agent, rag_assistant, visualizer_agent, xml_threat_model_reviewer],
            messages=[],
            max_round=100,
            speaker_transitions_type="allowed",
            allowed_or_disallowed_speaker_transitions={
                user_agent: [rag_assistant, visualizer_agent, xml_threat_model_reviewer],
                rag_assistant: [user_agent],
                visualizer_agent: [user_agent],
                xml_threat_model_reviewer: [user_agent],
            },
        )
        
        return group
    
    def setup_threat_modeling_assistant(self, context: TurnContext, state: AppTurnState, user_agent: Agent) -> Agent:
        def terminate_chat(message):
            message_sender_name = message.get("name", "")
            return message_sender_name != user_agent.name
        assistant = AssistantAgent(
            name="Threat_Model_Evaluator",
            description="An agent that manages a group chat for threat modeling validation and evaluation but should never be used the user does requests XML validation, ONLY when the user requests image validateion.",
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