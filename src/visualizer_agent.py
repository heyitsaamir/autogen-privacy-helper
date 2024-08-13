from typing import List, Annotated, Dict, Tuple, Union, Literal
from autogen import AssistantAgent, ConversableAgent, Agent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent
from threat_model_visualizer import ThreatModelImageAddToMessageCapability, Hints_To_Send
from autogen_utils import ImmediateExecutorCapability
from pydantic import BaseModel
from svg_to_png.lib.ThreatModel import User_Friendly_Block_Types


class Spec(BaseModel):
    id: int
    spec: str
    instructions_to_solve: str
    hints_to_send: Union[List[User_Friendly_Block_Types],
                         Literal["all"]] = "all"

    def build_instruction(self):
        return f"Spec id {self.id} - {self.spec}\n{self.instructions_to_solve}"


specs = [
    Spec(id=1, spec="All nodes should be inside a trust boundary", instructions_to_solve="""
A node is a box or a node surrounded by a black border. A trust boundary is a red boundary. A trust boundary can also be a concave line (this is a lined-trust boundary). The nodes that are inside the concave line are inside a lined-trust boundary.
You should ensure that all nodes are inside a trust boundary. If any node is outside a trust boundary, indicate which node. in your response.
""", hints_to_send=["Trust Boundary", "Node"]),
    Spec(id=2, spec="The data flow should be easy to understand", instructions_to_solve="""
The data flow is indicated by arrows. Each arrow has an associated label key inside a green box. The labels should collectively indicate the sequence of the data flow for the entire threat model.
You should ensure that all have label keys and each label key as a label with a sequence indicator (for example a number at the beginning of the label). 
If any arrow does not have a label key, indicate which arrow. If all arrows do not have label keys with corresponding labels with a sequence hint, indicate so in your response.
Otherwise, in your response indicate the sequence of the data flow for the entire threat model (i.e. the data flows from Node 1 to Node 2 to Node 3 etc.) Do not forget to use actual names of nodes rather than Node 1, Node 2 etc.
""", hints_to_send=["Node", "Data Flow"])
]


class SpecAnswer(BaseModel):
    spec_id: Annotated[int, "The spec id to answer"]
    detailed_answer: Annotated[str, "The answer to the spec question"]
    steps_to_improve: Annotated[str,
                                "Highly specific steps to improve if any. Use 'None' if no steps to improve"]


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
            # number_of_answers = len(self.spec_index_to_answer)
            return original_term_msg(x) or self.spec_index >= len(self.specs)
        agent._is_termination_msg = new_term_msg

    def _send_question(self, self2, messages, sender, config):
        if self.spec_index < len(self.specs):
            print(f"Sending question for spec {
                  self.specs[self.spec_index].id}")
            message = f"{self.specs[self.spec_index].build_instruction()}"
            self.spec_index += 1
            return [True, message]
        return [False, None]

    def add_answer(self, answer: SpecAnswer) -> Annotated[str, "The detailed answer to the spec question"]:
        self.spec_index_to_answer[answer.spec_id] = answer
        return answer.detailed_answer

def setup_visualizer_agent(llm_config, context, state):
    # go through each spec
    # augment with image etc
    # answer the question
    # extract how well it did and any action steps
    questioner_agent = AssistantAgent(
        name="Questioner"
    )
    cap = EvaluateSpecCapability(specs=specs)
    cap.add_to_agent(questioner_agent)

    answerer_agent = MultimodalConversableAgent(
        name="Answerer",
        system_message="""You are an answering agent.
You will *never* speculate or infer anything that is not in the threat model picture.
The threat model indicates the flow of data in a bigger system. You do not have any context about the system, but you can answer questions regarding the data flow present in the threat model.
Answer the questions as clearly and concisely as possible. Always use add_answer to add an answer to a spec question.
            """,
        description="A answerer agent that can exclusively answer questions based on a threat model picture.",
        llm_config={"config_list": [llm_config],
                    "timeout": 60, "temperature": 0},
    )
    ThreatModelImageAddToMessageCapability(
        context, say_when_evaluating=True, state=state, max_width=700).add_to_agent(answerer_agent)

    def add_answer(answer: Annotated[SpecAnswer, "The answer to the spec question"]) -> Annotated[str, "The detailed answer to the spec question"]:
        return cap.add_answer(answer)
    ImmediateExecutorCapability().add_to_agent(answerer_agent, add_answer,
                                               description="Add an answer to a spec question")

    assistant = AssistantAgent(
        name="Threat_Model_Evaluator",
        description="An agent that evaluates the quality of a threat model.",
    )

    def summarize(self, recipient, summary_args):
        # convert cap.spec_index_to_answer to array
        # then sort by spec id
        spec_answers: List[Tuple[Spec, SpecAnswer]] = []
        for spec_id, spec_answer in cap.spec_index_to_answer.items():
            spec_question = next(filter(lambda x: x.id == spec_id, specs))
            spec_answers.append((spec_question, spec_answer))
        spec_answers = sorted(spec_answers, key=lambda x: x[1].spec_id)
        result = ''
        for spec_answer_tuple in spec_answers:
            spec, spec_answer = spec_answer_tuple
            header = f"## {spec.spec}"
            spec_answer_detailed = spec_answer.detailed_answer
            spec_answer_improve = f'### Steps to improve\n{
                spec_answer.steps_to_improve}' if spec_answer.steps_to_improve != "None" else None
            result += f"{header}\n{spec_answer_detailed}{f'\n{spec_answer_improve}' if spec_answer_improve else ''}\n\n\n"

        return result

    assistant.register_nested_chats([
        {
            "recipient": questioner_agent,
            "sender": answerer_agent,
            "summary_method": summarize,
        },
    ], trigger=lambda sender: sender not in [assistant])

    return assistant
