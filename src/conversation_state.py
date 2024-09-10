from abc import ABC, abstractmethod
from typing import List

class ConversationState(ABC):
    @abstractmethod
    def get_file_content(self, index: int = 0) -> bytes:
        pass

    @abstractmethod
    def get_file_content_type(self, index: int = 0) -> str:
        pass

    @abstractmethod
    def has_input_files(self) -> bool:
        pass

    @abstractmethod
    def get_threat_model_evaluator_type(self) -> str:
        pass

class ChatContext(ABC):
    @abstractmethod
    def has_conversation_id(self) -> bool:
        pass

    @abstractmethod
    def get_conversation_id(self) -> str:
        pass

    @abstractmethod
    async def add_content(self, message_text: str, content_type: str, content_url: str):
        pass

# Implements the a local version of ConversationState
class LocalConversationState(ConversationState):

    def __init__(self, contents: List[bytes], content_types: List[str], threat_model_evaluator_type: str):
        self.contents = contents
        self.content_types = content_types
        self.threat_model_evaluator_type = threat_model_evaluator_type

    def get_file_content(self, index: int = 0) -> bytes:
        return self.contents[index]

    def get_file_content_type(self, index: int = 0) -> str:
        return self.content_types[index]

    def has_input_files(self) -> bool:
        return bool(self.contents)

    def get_threat_model_evaluator_type(self) -> str:
        return self.threat_model_evaluator_type

class ChatContent:
    def __init__(self, message_text: str, content_type: str, content_url: str):
        self._message_text = message_text
        self._content_type = content_type
        self._content_url = content_url

    def get_message_text(self) -> str:
        return self._message_text

    def get_content_type(self) -> str:
        return self._content_type

    def get_content_url(self) -> str:
        return self._content_url

class LocalChatContext(ChatContext):

    def __init__(self):
        self.chat_content = []

    def has_conversation_id(self) -> bool:
        return False

    def get_conversation_id(self) -> str:
        return ""

    async def add_content(self, message_text: str, content_type: str, content_url: str):
        self.chat_content.append(ChatContent(message_text, content_type, content_url))

    def get_content(self) -> List[ChatContent]:
        return self.chat_content
