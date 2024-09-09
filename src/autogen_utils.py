from typing import Callable, Any, Optional
from autogen import ConversableAgent, register_function, Agent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from teams.typing import Typing as TeamsTyping
from botbuilder.core import TurnContext
from conversation_state import ConversationState, ChatContext
from state import AppTurnState
from botbuilder.schema import Activity, ActivityTypes, Attachment
from abc import ABC, abstractmethod

class StoppableAgentCapability(AgentCapability, ABC):
    @abstractmethod
    def stop(self):
        pass


class ImmediateExecutorCapability(AgentCapability):
    def __init__(self):
        super().__init__()

    def add_to_agent(
        self,
        caller_agent: ConversableAgent,
        f: Callable[..., Any],
        description: str,
        name: Optional[str] = None,
    ):
        register_function(
            f,
            caller=caller_agent,
            executor=caller_agent,
            description=description,
            name=name,
        )
        caller_agent.register_hook(
            "process_message_before_send", self._process_message_before_send
        )

    def _process_message_before_send(
        self, message, sender: ConversableAgent, recipient, silent
    ):
        if isinstance(message, dict):
            _, res = sender.generate_tool_calls_reply([message], sender)
            return res.get("content") if isinstance(res, dict) else "Answered"
        return message

class TypingCapability(StoppableAgentCapability):
    def __init__(self, context: TurnContext):
        self.typing = TeamsTyping()
        self.context = context
        super().__init__()

    def add_to_agent(self, agent: ConversableAgent):
        agent.register_reply([Agent, None], self._send_typing)
        agent.register_hook("process_all_messages_before_reply", self._stop_typing)

    async def _send_typing(self, self2, messages, sender, config):
        self.typing.stop()
        await self.typing.start(self.context)
        return [False, None]

    def _stop_typing(self, messages):
        self.typing.stop()
        return messages
    
    def stop(self):
        self.typing.stop()
    
# An implementation of ConversationState that takes an AppTurnState
class AppTurnStateConversationState(ConversationState):

    def __init__(self, state: AppTurnState):
        self.state = state
    
    def get_file_content(self, index: int = 0) -> bytes:
        return self.state.temp.input_files[index].content

    def get_file_content_type(self, index: int = 0) -> str:
        return self.state.temp.input_files[index].content_type

    def has_input_files(self) -> bool:
        return self.state.temp.input_files is not None and len(self.state.temp.input_files) > 0
    
    def get_threat_model_evaluator_type(self) -> str:
        return self.state.conversation.get(
            "threat_model_evaluator", "xml_multi_prompt"
        )    
    
class TurnChatContext(ChatContext):

    def __init__(self, context: TurnContext):
        self.context = context

    def has_conversation_id(self) -> bool:
        return self.context.activity.conversation is not None

    def get_conversation_id(self) -> str:
        return self.context.activity.conversation.id

    async def add_content(self, message_text: str, content_type: str, content_url: str):
        await self.context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        text=message_text,
                        attachments=[
                            Attachment(
                                content_type=content_type,
                                content_url=content_url,
                            )
                        ],
                    )
                )

    

