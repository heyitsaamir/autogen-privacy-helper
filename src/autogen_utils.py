from typing import Callable, Any, Optional
from autogen import ConversableAgent, register_function, Agent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from teams.typing import Typing as TeamsTyping
from botbuilder.core import TurnContext


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


class TypingCapability(AgentCapability):
    def __init__(self, context: TurnContext, typing: TeamsTyping):
        self.typing = typing
        self.context = context
        super().__init__()

    def add_to_agent(self, agent: ConversableAgent):
        agent.register_reply([Agent, None], self._send_typing)
        agent.register_hook("process_all_messages_before_reply", self._stop_typing)

    async def _send_typing(self, self2, messages, sender, config):
        await self.typing.start(self.context)
        return [False, None]

    def _stop_typing(self, messages):
        self.typing.stop()
        return messages
