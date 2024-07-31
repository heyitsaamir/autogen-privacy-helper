from datetime import datetime
from typing import List, Union, Annotated, Tuple
from autogen.agentchat.contrib.vectordb.base import QueryResults, VectorDB, Document
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent
from autogen import AssistantAgent, register_function
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.core.exceptions import ResourceNotFoundError
from config import Config

def build_config(suffix: str, previous_day: bool = False):
    # Get the current date
    current_date = datetime.now()

    # Format the date as YYYYMMDD
    day = current_date.day - 1 if previous_day else current_date.day
    formatted_date_without_day = current_date.strftime("%Y%m")
    formatted_date = f"{formatted_date_without_day}{day:02d}"

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
    
    def _search(self, query: str, retry_with_previous_day: bool = False):
        search_endpoint = Config.AZURE_SEARCH_SERVICE_ENDPOINT
        # index name is YYYYMMDD-1-home-index
        index_name = build_config("1-home-index", previous_day=retry_with_previous_day)
        api_key = Config.AZURE_SEARCH_API_KEY
        semantic_search_config = build_config("1-home-index-sc", previous_day=retry_with_previous_day)
        
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
            if retry_with_previous_day is False and isinstance(e, ResourceNotFoundError):
                print(f"Resource not found error. Retrying with previous day.")
                return self._search(query, retry_with_previous_day=True)
            raise e
            
        output = []
        for result in response:
            output.append(result)
        return output
    
class RagExecutorAgent(AssistantAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def check_if_rag_completed(**kwargs):
            message = kwargs.get("message")
            self = kwargs.get("sender")
            recipient = kwargs.get("recipient")
            if message == "NOT_A_TOOL_RESPONSE":
                # get the last message from the recipient
                last_message = recipient.last_message(self)
                # copy the last_message object
                new_message = last_message.copy()
                # get or create a context dict
                context = new_message.get("context", {})
                # set the content to the last message content
                context["should_end"] = True
                new_message["context"] = context
                return new_message
            return message
        self.hook_lists["process_message_before_send"].append(
            check_if_rag_completed)

def setup_rag_assistant(llm_config):
    db = AzureAISearch()
    def did_retrieve_content(msg):
        should_end = msg.get("context", {}).get("should_end", False)
        return should_end is True
    rag_proxy_agent = RetrieveUserProxyAgent(
        name="rag_proxy_agent",
        human_input_mode="NEVER",
        retrieve_config={
            "task": "qa",
            "vector_db": db,
        },
    )
    
    rag_executor_agent = RagExecutorAgent(
        name="rag_executor",
        system_message="Executes the rag using the retrieve_content function.",
        default_auto_reply="NOT_A_TOOL_RESPONSE",
    )

    assistant = AssistantAgent(
        name="System_Details_Answerer",
        system_message="""You are a system details answerer agent.
Your role is is to answer answers about the overall system. You are able to look up details about the system.""",
        description="A system details answerer agent that can answer questions about the overall system.",
        llm_config=llm_config,
        is_termination_msg=did_retrieve_content
    )
    
    def retrieve_content(
        message: Annotated[
            str,
            "Refined message which can be used to retrieve details about the system. Use precise language to get the best results.",
        ],
        n_results: Annotated[int, "number of results"] = 3,
    ) -> str:
        rag_proxy_agent.n_results = n_results  # Set the number of results to be retrieved.
        # Check if we need to update the context.
        update_context_case1, update_context_case2 = rag_proxy_agent._check_update_context(message)
        if (update_context_case1 or update_context_case2) and rag_proxy_agent.update_context:
            rag_proxy_agent.problem = message if not hasattr(rag_proxy_agent, "problem") else rag_proxy_agent.problem
            _, ret_msg = rag_proxy_agent._generate_retrieve_user_reply(message)
        else:
            _context = {"problem": message, "n_results": n_results}
            ret_msg = rag_proxy_agent.message_generator(rag_proxy_agent, None, _context)
        return ret_msg if ret_msg else message
    
    def trigger(sender):
        return sender not in [rag_executor_agent] # To prevent the assistant from triggering itself
    
    assistant.register_nested_chats([
        {
            "recipient": assistant,
            "sender": rag_executor_agent,
            "summary_method": "last_msg",
        },
    ], trigger=trigger)

    register_function(retrieve_content, caller=assistant, executor=rag_executor_agent, description="Retrieve content for asking user questions.")
        
    return assistant