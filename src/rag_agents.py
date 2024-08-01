from datetime import datetime, timedelta
import re
from typing import List, Union, Tuple
from autogen.agentchat.contrib.vectordb.base import QueryResults, VectorDB, Document
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent
from autogen.agentchat.contrib.retrieve_assistant_agent import RetrieveAssistantAgent
from autogen import AssistantAgent, ConversableAgent
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.core.exceptions import ResourceNotFoundError
from config import Config

def build_config(suffix: str, previous_day_index: int = 0):
    # Get the current date
    date = datetime.now()
    date = date - timedelta(days=previous_day_index)

    # Format the date as YYYYMMDD
    formatted_date = date.strftime("%Y%m%d")

    # Construct the final string
    return f"{formatted_date}-{suffix}"
    

class AzureAISearch(VectorDB):
    def create_collection(self, collection_name: str, overwrite: bool = False, get_or_create: bool = True):
        pass
    
    def get_collection(self, collection_name: str = None):
        pass
    
    def delete_collection(self, collection_name: str):
        pass
    
    def insert_docs(self, docs: List[Document], collection_name: str = None, upsert: bool = False, **kwargs):
        pass
    
    def update_docs(self, docs: List[Document], collection_name: str = None, **kwargs):
        pass
    
    def delete_docs(self, doc_ids: List[str], collection_name: str = None):
        pass
    
    def get_docs_by_ids(self, doc_ids: List[str], collection_name: str = None):
        pass
    
    def retrieve_docs(self,
        queries: List[str],
        collection_name: Union[str, None] = None,
        n_results: int = 10,
        distance_threshold: float = 0,
        **kwargs,
    ) -> QueryResults:
        documents_all: List[List[Tuple[Document, float]]] = []
        count = 0
        for query in queries:
            documents: List[Tuple[Document, float]] = []
            for result in self._search(query):
                documents.append(({
                    "id": result["id"],
                    "content": " ".join(c.text for c in result["@search.captions"]),
                    "metadata": None,
                    "embedding": None
                }, result["@search.score"]))
                count = count + 1
            documents_all.append(documents)
        return documents_all
    
    def _search(self, query: str, previous_day_index: int = 0):
        print("Performing search!")
        search_endpoint = Config.AZURE_SEARCH_SERVICE_ENDPOINT
        # index name is YYYYMMDD-1-home-index
        index_name = build_config("1-home-index", previous_day_index=previous_day_index)
        api_key = Config.AZURE_SEARCH_API_KEY
        semantic_search_config = build_config("1-home-index-sc", previous_day_index=previous_day_index)
        
        if not api_key:
            raise ValueError("No Azure Search API key provided.")
        
        search_client = SearchClient(search_endpoint, index_name, AzureKeyCredential(api_key))
        try:
            raw_response = search_client.search(search_text=query,
                query_type="semantic",
                semantic_configuration_name=semantic_search_config,
                query_caption="extractive",
                query_answer="extractive|count-3",
                top=5)
            response = list(raw_response)
        except Exception as e:
            if previous_day_index <= 2 and isinstance(e, ResourceNotFoundError):
                print(f"Resource not found error. Retrying with previous day. (curr_day - {previous_day_index})")
                return self._search(query, previous_day_index=previous_day_index + 1)
            raise e
            
        output = []
        for result in response:
            output.append(result)
        return output

def setup_rag_assistant(llm_config):
    db = AzureAISearch()
    rag_proxy_agent = RetrieveUserProxyAgent(
        name="rag_proxy_agent",
        human_input_mode="NEVER",
        retrieve_config={
            "task": "qa",
            "vector_db": db,
        },
    )
    
    rag_assistant_agent = RetrieveAssistantAgent(
        name="rag_assistant",
        system_message="You are a helpful assistant.",
        llm_config=llm_config,
    )
    
    assistant = AssistantAgent(
        name="System_Details_Answerer",
        description="A system details answerer agent that can seach for information. It cannot do any evaluation for threat models.",
    )
    
    def extract_problem(message):
        match = re.search(r'<QUESTION[^>]*>\s*(.*?)\s*</QUESTION>', message)
        if match:
            return match.group(1)
        return message
        
    def message_generator(_recipient, messages, sender, _config):
        last_msg = messages[-1].get("content")
        if sender is assistant:
            _context = {"problem": extract_problem(last_msg), "n_results": 3}
            return rag_proxy_agent.message_generator(rag_proxy_agent, messages, _context)
        else:
            return last_msg
    
    rag_assistant_agent.register_nested_chats([
        {
            "recipient": rag_assistant_agent,
            "sender": rag_proxy_agent,
            "summary_method": "last_msg",
            "message": message_generator
        },
    ], trigger=assistant)
    
    def trigger(sender):
        return sender not in [assistant] # To prevent the assistant from triggering itself
    
    def custom_summary_method(
                sender: ConversableAgent,
                recipient: ConversableAgent,
                summary_args: dict,
            ):
                last_msg = recipient.last_message(sender)
                if last_msg:
                    last_msg_content = last_msg.get("content", None)
                    if last_msg_content == '':
                        return 'I do not know.'
                return last_msg
    
    assistant.register_nested_chats([
        {
            "recipient": rag_assistant_agent,
            "sender": assistant,
            "summary_method": custom_summary_method,
            "max_turns": 1,
        },
    ], trigger=trigger)
        
    return assistant