import argparse
import asyncio
from config import Config
from privacy_review_assistant_group import PrivacyReviewAssistantGroup
from conversation_state import LocalChatContext, LocalConversationState
from autogen import GroupChatManager, ConversableAgent
from typing import Dict, Optional, Union, Literal
import base64
import io

def data_uri_to_bytes(data_uri) -> bytes:
    # Strip the data URI prefix
    header, encoded = data_uri.split(",", 1)
    # Decode the base64 string
    image_data = base64.b64decode(encoded)
    # Convert the decoded bytes to a PIL image
    return io.BytesIO(image_data).read()

# Agent that always responds with "terminate"
class TerminateAgent(ConversableAgent):
    def __init__(self, name: str, llm_config: Optional[Union[Dict, Literal[False]]], code_execution_config: Union[Dict, Literal[False]], human_input_mode: Literal["ALWAYS", "NEVER", "TERMINATE"]):
        super().__init__(name, llm_config=llm_config, code_execution_config=code_execution_config, human_input_mode=human_input_mode)

    async def a_initiate_chat(self, recipient, message, clear_history=False):
        # Always respond with "terminate"
        return {"content": "terminate"}

async def process_file(input_file, evaluation_type, output_image_file, output_result_text_file):
    config = Config()
    llm_config = config.build_llm_config()

    if config.OPENAI_KEY is None and config.AZURE_OPENAI_KEY is None:
        raise RuntimeError(
            "Unable to build LLM config - please check that OPENAI_KEY or AZURE_OPENAI_KEY is set."
        )
    threat_model_reviewer_group = PrivacyReviewAssistantGroup(llm_config=llm_config)
    context = LocalChatContext()
    with open(input_file, "rb") as file:
        file_bytes = file.read()
    state = LocalConversationState([file_bytes], ["text/xml"], evaluation_type)
    terminating_agent = ConversableAgent(
        name="TerminatingAgent",
        llm_config=False,
        system_message="A terminating agent that always responds with 'TERMINATE'",
        code_execution_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: True
    )

    def always_terminate(self, messages, sender, config):
        return True, {"content": "TERMINATE"}
    
    terminating_agent.register_reply([ConversableAgent, None], always_terminate, remove_other_reply_funcs=True)

    groupchat = threat_model_reviewer_group.group_chat_builder(context, state, terminating_agent)
    manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

    chat_result = await terminating_agent.a_initiate_chat(
        recipient=manager, message="Please validate this threat model.", clear_history=False
    )
    print(context.get_content())
    first_item = context.get_content()[0]
    content_url = first_item.get_content_url()
    image_bytes = data_uri_to_bytes(content_url)
    with open(output_image_file, "wb") as file:
        file.write(image_bytes)
    
    second_to_last_item = chat_result.chat_history[-2]
    with open(output_result_text_file, "w") as file:
        file.write(second_to_last_item["content"])



if __name__ == "__main__":
    # Create an argument parser
    parser = argparse.ArgumentParser(description="Process file and save results.")
    
    # Add the command line arguments
    parser.add_argument("input_file", help="Path to the input file")
    parser.add_argument("output_image_file", help="Path to the output image file")
    parser.add_argument("output_result_text_file", help="Path to the output result text file")
    parser.add_argument(
        "evaluation_type",
        choices=["xml_single_prompt", "xml_multi_prompt", "visual"],
        default="xml_multi_prompt",
        help="Type of evaluation (default: xml_multi_prompt)",
    )
    
    args = parser.parse_args()
    
    asyncio.run(process_file(args.input_file, args.evaluation_type, args.output_image_file, args.output_result_text_file))
