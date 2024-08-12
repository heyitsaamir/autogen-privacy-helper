from typing import Callable, Any, Optional
from autogen import ConversableAgent, register_function
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability

class ImmediateExecutorCapability(AgentCapability):
    def __init__(self):
        super().__init__()
        
    def add_to_agent(self, caller_agent: ConversableAgent, f: Callable[..., Any], description: str, name: Optional[str] = None):
        register_function(f, caller=caller_agent, executor=caller_agent, description=description, name=name)
        caller_agent.register_hook('process_message_before_send', self._process_message_before_send)
        
    def _process_message_before_send(self, message, sender: ConversableAgent, recipient, silent):
        if isinstance(message, dict):
            _, res = sender.generate_tool_calls_reply([message], sender)
            return res.get("content") if isinstance(res, dict) else "Answered"
        return message