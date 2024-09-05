import json
from typing import List, Annotated, Dict, Tuple, Union, Literal
from autogen import AssistantAgent, ConversableAgent, Agent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from autogen_utils import ImmediateExecutorCapability
from pydantic import BaseModel
from xml_threat_model_reviewer import XMLThreatModelImageAddToMessageCapability
from Spec import Spec, load_specs_from_json

specs = load_specs_from_json("src/specs.json")


def build_instruction(spec: Spec):
    return f"""Now, based on the given details of the spec model, see if it fulfills this criteria\nSpec id {spec.id}\n{spec.instructions_to_solve}
If the criteria is not met, then {spec.improvement_hints}
"""


tag_with_headers = {"green": "✅", "red": "❌", "yellow": "⚠️"}


class SpecAnswer(BaseModel):
    spec_id: Annotated[int, "The spec id to answer"]
    detailed_answer: Annotated[
        str, "Does the threat model meet the spec criteria? Why or why not? Be helpful and specific."
    ]
    steps_to_improve: Annotated[
        str,
        "What are exact steps to improve the threat model to meet the spec criteria? Use 'None' if no steps to improve",
    ]
    tag: Annotated[
        Union[
            Annotated[Literal["green"], "Spec criteria is met"],
            Annotated[Literal["red"], "Items needs to be fixed to meet criteria"],
            Annotated[Literal["yellow"], "Criteria is met but can be improved"],
        ],
        "The tag of the spec answer",
    ]


class EvaluateSpecCapability(AgentCapability):
    def __init__(self, specs: List[Spec]):
        self.specs = specs
        self.spec_index = 0
        self.spec_index_to_answer: Dict[int, SpecAnswer] = {}
        super().__init__()

    def add_to_agent(self, agent: ConversableAgent):
        agent.register_reply([Agent, None], self._send_question)
        original_term_msg = agent._is_termination_msg

        def new_term_msg(x):
            return original_term_msg(x) or self.spec_index >= len(self.specs)

        agent._is_termination_msg = new_term_msg

    async def _send_question(self, self2, messages, sender, config):
        if self.spec_index < len(self.specs):
            print(f"Sending question for spec {self.specs[self.spec_index].id}")
            message = f"{build_instruction(self.specs[self.spec_index])}"
            self.spec_index += 1
            return [True, message]
        return [False, None]

    def add_answer(
        self, answer: SpecAnswer
    ) -> Annotated[str, "The detailed answer to the spec question"]:
        self.spec_index_to_answer[answer.spec_id] = answer
        return answer.detailed_answer

class ClearHistoryCapability(AgentCapability):
    def __init__(self):
        super().__init__()

    def add_to_agent(self, agent: ConversableAgent):
        agent.register_hook("process_all_messages_before_reply", self._clear_history)
        
    def _clear_history(self, messages):
        return [messages[-1]]

def setup_xml_threat_model_reviewer(llm_config, context, state):
    questioner_agent = AssistantAgent(name="Questioner")
    cap = EvaluateSpecCapability(specs=specs)
    cap.add_to_agent(questioner_agent)

    answerer_agent = AssistantAgent(
        name="Answerer",
        system_message="""You are an answering agent.
You will *NEVER* speculate or infer anything that is not in the details of the threat model provided to you.
The threat model indicates the flow of data in a bigger system. You do not have any context about the system, but you can answer questions regarding the data flow present in the threat model.
Answer the questions as clearly and concisely as possible. Always use add_answer to add an answer to a spec question.
            """,
        description="A answerer agent that can exclusively answer questions based on a threat model picture.",
        llm_config={"config_list": [{**llm_config, "tool_choice": "required"}], "timeout": 60, "temperature": 0},
    )
    ClearHistoryCapability().add_to_agent(answerer_agent)
    XMLThreatModelImageAddToMessageCapability(
        context, say_when_evaluating=True, state=state, max_width=400, set_message_to_second_last=True
    ).add_to_agent(answerer_agent)

    def add_answer(
        spec_id: Annotated[int, "The spec id to answer"],
        detailed_answer: Annotated[
            str, "Does the threat model meet the spec criteria? Why or why not? Be helpful and specific."
        ],
        steps_to_improve: Annotated[
            str,
            "What are exact steps to improve the threat model to meet the spec criteria? Use 'None' if no steps to improve",
        ],
        tag: Annotated[
            Union[
                Annotated[Literal["green"], "Spec criteria is met"],
                Annotated[Literal["red"], "Items needs to be fixed to meet criteria"],
                Annotated[Literal["yellow"], "Criteria is met but can be improved"],
            ],
            "The tag of the spec answer",
        ]
    ) -> Annotated[str, "The detailed answer to the spec question"]:
        return cap.add_answer(SpecAnswer(spec_id=spec_id, detailed_answer=detailed_answer, steps_to_improve=steps_to_improve, tag=tag))

    ImmediateExecutorCapability().add_to_agent(
        answerer_agent, add_answer, description="Add an answer to a spec question"
    )

    assistant = AssistantAgent(
        name="Threat_Model_Evaluator",
        description="An agent that evaluates the quality of a threat model.",
    )

    def summarize(self, recipient, summary_args):
        spec_answers: List[Tuple[Spec, SpecAnswer]] = []
        for spec_id, spec_answer in cap.spec_index_to_answer.items():
            spec_question = next(filter(lambda x: x.id == spec_id, specs))
            spec_answers.append((spec_question, spec_answer))
        spec_answers = sorted(spec_answers, key=lambda x: x[1].spec_id)

        containers = [
            build_container_for_answer(spec, spec_answer)
            for spec, spec_answer in spec_answers
        ]
        card = build_adaptive_card(containers)

        def set_default(obj):
            if isinstance(obj, set):
                return list(obj)
            raise TypeError

        return (
            f"adaptive_card:{json.dumps(card, ensure_ascii=False, default=set_default)}"
        )

    assistant.register_nested_chats(
        [
            {
                "recipient": questioner_agent,
                "sender": answerer_agent,
                "summary_method": summarize,
                "chat_id": 1,
            },
        ],
        trigger=lambda sender: sender not in [assistant],
        use_async=True,
    )

    return assistant


def build_container_for_answer(spec: Spec, spec_answer: SpecAnswer):
    answer_items = [
        {
            "type": "TextBlock",
            "text": spec_answer.detailed_answer,
            "wrap": True,
        }
    ]
    if spec_answer.steps_to_improve != "None" and spec_answer.steps_to_improve:
        answer_items.append(
            {
                "type": "TextBlock",
                "text": "Steps to improve:",
                "wrap": True,
                "weight": "Bolder",
            }
        )
        answer_items.append(
            {
                "type": "TextBlock",
                "text": spec_answer.steps_to_improve,
                "wrap": True,
            }
        )
    return {
        "type": "Container",
        "items": [
            {
                "type": "TextBlock",
                "text": spec.spec,
                "wrap": True,
                "weight": "Bolder",
            },
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": tag_with_headers[spec_answer.tag],
                                "wrap": True,
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": answer_items,
                    },
                ],
            },
        ],
        "separator": True,
    }


def build_adaptive_card(spec_answer_containers: List[Dict]):
    body = [
        {
            "type": "TextBlock",
            "text": "Threat model review",
            "wrap": True,
            "weight": "Bolder",
            "style": "heading",
        },
        *spec_answer_containers,
    ]
    return {
        "type": "AdaptiveCard",
        "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body,
    }
