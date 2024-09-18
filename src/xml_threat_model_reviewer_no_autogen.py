import json
import os
from typing import Dict

from autogen import Agent, AssistantAgent, ConversableAgent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from conversation_state import ChatContext, ConversationState
from models import (
    Spec,
    load_specs_from_json,
)
from no_autogen_spec_solver import ThreatModelValidator

folder = os.path.dirname(os.path.abspath(__file__))
specs = load_specs_from_json(f"{folder}/specs.json")


def build_instruction(spec: Spec):
    return f"""Now, based on the given details of the spec model, see if it fulfills this criteria\nSpec id {spec.id}\n{spec.instructions_to_solve}
"""


class ValidateSpecsWithoutAutogenCapability(AgentCapability):
    def __init__(
        self, llm_config: Dict, context: ChatContext, state: ConversationState
    ):
        self.context = context
        self.state = state
        self.validator = ThreatModelValidator(llm_config)
        super().__init__()

    def add_to_agent(self, agent: ConversableAgent):
        agent.register_reply(
            [Agent, None], self._validate, remove_other_reply_funcs=True
        )

    async def _validate(self, self2, messages, sender, config):
        result = await self.validator.handle_request(self.context, self.state)
        if result is None:
            return [True, "Unable to validate threat model"]

        def set_default(obj):
            if isinstance(obj, set):
                return list(obj)
            raise TypeError

        return [
            True,
            f"adaptive_card:{json.dumps(result, ensure_ascii=False, default=set_default)}",
        ]


class ClearHistoryCapability(AgentCapability):
    def __init__(self):
        super().__init__()

    def add_to_agent(self, agent: ConversableAgent):
        agent.register_hook("process_all_messages_before_reply", self._clear_history)

    def _clear_history(self, messages):
        return [messages[-1]]


def setup_xml_threat_model_reviewer(llm_config, context, state):
    assistant = AssistantAgent(
        name="Threat_Model_Evaluator",
        description="An agent that evaluates the quality of a threat model.",
    )

    capability = ValidateSpecsWithoutAutogenCapability(llm_config, context, state)
    capability.add_to_agent(assistant)

    return assistant
