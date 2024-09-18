from typing import Optional

from autogen import Agent, AssistantAgent, GroupChat
from autogen_utils import StoppableAgentCapability
from conversation_state import ChatContext, ConversationState
from rag_agents import setup_rag_assistant
from threat_model_visualizer import ThreatModelImageVisualizerCapability
from visualizer_agent import setup_visualizer_agent
from xml_threat_model_reviewer import (
    setup_xml_threat_model_reviewer as setup_xml_threat_model_reviewer_single_prompt,
)
from xml_threat_model_reviewer2 import (
    setup_xml_threat_model_reviewer as setup_xml_threat_model_reviewer_multi_prompt,
)
from xml_threat_model_reviewer_no_autogen import (
    setup_xml_threat_model_reviewer as setup_xml_threat_model_reviewer_no_autogen,
)


class PrivacyReviewAssistantGroup:
    def __init__(self, llm_config):
        self.llm_config = llm_config

    def group_chat_builder(
        self, context: ChatContext, state: ConversationState, user_agent: Agent, typing_capability: Optional[StoppableAgentCapability] = None
    ) -> GroupChat:
        threat_model_evaluator_type = state.get_threat_model_evaluator_type()
        rag_assistant = setup_rag_assistant(self.llm_config)
        if threat_model_evaluator_type == "xml_single_prompt":
            threat_modeling_assistant = setup_xml_threat_model_reviewer_single_prompt(
                self.llm_config, context, state
            )
        elif threat_model_evaluator_type == "visual":
            threat_modeling_assistant = setup_visualizer_agent(
                self.llm_config, context, state
            )
        elif threat_model_evaluator_type == "no_autogen":
            threat_modeling_assistant = setup_xml_threat_model_reviewer_no_autogen(
                self.llm_config, context, state
            )
        else:
            threat_modeling_assistant = setup_xml_threat_model_reviewer_multi_prompt(
                self.llm_config, context, state, typing_capability
            )
        visualizer_agent = self.setup_visualizer_assistant(context, state, user_agent)
        group = GroupChat(
            agents=[
                user_agent,
                rag_assistant,
                visualizer_agent,
                threat_modeling_assistant,
            ],
            messages=[],
            max_round=100,
            speaker_transitions_type="allowed",
            allowed_or_disallowed_speaker_transitions={
                user_agent: [
                    rag_assistant,
                    visualizer_agent,
                    threat_modeling_assistant,
                ],
                rag_assistant: [user_agent],
                visualizer_agent: [user_agent],
                threat_modeling_assistant: [user_agent],
            },
        )

        return group

    def setup_visualizer_assistant(
        self, context: ChatContext, state: ConversationState, _user_agent: Agent
    ) -> Agent:
        visualizer_assistant = AssistantAgent(
            name="Visualizer",
            description="An agent that visualizes the threat model.",
        )
        visualizer_capability = ThreatModelImageVisualizerCapability(
            context=context, state=state
        )
        visualizer_capability.add_to_agent(visualizer_assistant)
        return visualizer_assistant
