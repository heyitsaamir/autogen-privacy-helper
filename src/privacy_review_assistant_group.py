from autogen import AssistantAgent, GroupChat, GroupChatManager, Agent

from botbuilder.core import TurnContext

from state import AppTurnState
from rag_agents import setup_rag_assistant
from threat_model_reviewer_group import ThreatModelReviewerGroup

class PrivacyReviewAssistantGroup:
    def __init__(self, llm_config):
        self.llm_config = llm_config
        
    def group_chat_builder(self, context: TurnContext, state: AppTurnState, user_agent: Agent) -> GroupChat:
        rag_assistant = setup_rag_assistant(self.llm_config)
        threat_modeling_assistant = self.setup_threat_modeling_assistant(context, state, user_agent)
        group = GroupChat(
            agents=[user_agent, rag_assistant, threat_modeling_assistant],
            messages=[],
            max_round=100,
            speaker_transitions_type="allowed",
            allowed_or_disallowed_speaker_transitions={
                user_agent: [rag_assistant, threat_modeling_assistant],
                rag_assistant: [user_agent],
                threat_modeling_assistant: [user_agent],
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