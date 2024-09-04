"""
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the MIT License.
"""

from typing import Optional, List, Dict, Union, Literal

from botbuilder.core import Storage, TurnContext
from teams.state import ConversationState, TempState, TurnState, UserState
from datetime import datetime


class AppConversationState(ConversationState):
    message_history_old: Optional[List[Dict]] = None
    message_history: Optional[List[Dict]] = None
    is_waiting_for_user_input: bool = False
    started_waiting_for_user_input_at: Optional[Union[datetime, str]] = None
    spec_url: Optional[str] = None
    threat_model_evaluator: Union[
        Literal["visual"], Literal["xml_single_prompt"], Literal["xml_multi_prompt"]
    ]
    activity_id: Optional[str] = None

    @classmethod
    async def load(
        cls, context: TurnContext, storage: Optional[Storage] = None
    ) -> "AppConversationState":
        state = await super().load(context, storage)
        return cls(**state)

    async def clear(self, context: TurnContext) -> None:
        self.is_waiting_for_user_input = False
        self.started_waiting_for_user_input_at = None
        self.spec_url = None
        await self.save(context)


class AppTurnState(TurnState[AppConversationState, UserState, TempState]):
    conversation: AppConversationState

    @classmethod
    async def load(
        cls, context: TurnContext, storage: Optional[Storage] = None
    ) -> "AppTurnState":
        return cls(
            conversation=await AppConversationState.load(context, storage),
            user=await UserState.load(context, storage),
            temp=await TempState.load(context, storage),
        )
