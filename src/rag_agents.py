from typing import List, Union, Annotated, Tuple
from autogen.agentchat.contrib.vectordb.base import QueryResults, VectorDB, Document
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent
from autogen import AssistantAgent, register_function
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from config import Config

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
    
    def _search(self, query: str):
        search_endpoint = Config.AZURE_SEARCH_SERVICE_ENDPOINT
        index_name = Config.AZURE_SEARCH_INDEX_NAME
        api_key = Config.AZURE_SEARCH_API_KEY
        semantic_search_config = Config.AZURE_SEMANTIC_SEARCH_CONFIG
        
        if not api_key:
            raise ValueError("No Azure Search API key provided.")
        
        search_client = SearchClient(search_endpoint, index_name, AzureKeyCredential(api_key))
        raw_response = search_client.search(search_text=query,
                query_type="semantic",
                semantic_configuration_name=semantic_search_config,
                query_caption="extractive",
                query_answer="extractive|count-3",
                top=5)
        response = list(raw_response)
        output = []
        for result in response:
            output.append(result)
        return output

def setup_rag_assistant(llm_config):
    db = AzureAISearch()
    ragproxyagent = RetrieveUserProxyAgent(
        name="ragproxyagent",
        human_input_mode="NEVER",
        retrieve_config={
            "task": "qa",
            "vector_db": db,
        },
    )

    assistant = AssistantAgent(
        name="questionassistant",
        system_message="You are a helpful assistant in getting answers to the user's questions. Use",
    )
    
    internal_assistant = AssistantAgent(
        name="rag_executor",
        system_message="Executes the rag",
        llm_config=llm_config,
    )
    
    rag_assistant = AssistantAgent(
        name="rag_assistant",
        system_message="Use the retrieve_content function to get content for asking user questions.",
        llm_config=llm_config,
    )
    
    def retrieve_content(
        message: Annotated[
            str,
            "Refined message which keeps the original meaning and can be used to retrieve content for code generation and question answering.",
        ],
        n_results: Annotated[int, "number of results"] = 3,
    ) -> str:
        ragproxyagent.n_results = n_results  # Set the number of results to be retrieved.
        # Check if we need to update the context.
        update_context_case1, update_context_case2 = ragproxyagent._check_update_context(message)
        if (update_context_case1 or update_context_case2) and ragproxyagent.update_context:
            ragproxyagent.problem = message if not hasattr(ragproxyagent, "problem") else ragproxyagent.problem
            _, ret_msg = ragproxyagent._generate_retrieve_user_reply(message)
        else:
            _context = {"problem": message, "n_results": n_results}
            ret_msg = ragproxyagent.message_generator(ragproxyagent, None, _context)
        return ret_msg if ret_msg else message
    
    def trigger(sender): 
        return sender not in [rag_assistant, internal_assistant]
    
    assistant.register_nested_chats([
        {
            "recipient": rag_assistant,
            "sender": internal_assistant,
            "summary_method": "last_msg",
            "summary_prompt": "Use the retrieve_content function to get content for asking user questions.",
            "max_turns": 2
        },
    ], trigger=trigger)

    register_function(retrieve_content, caller=rag_assistant, executor=internal_assistant, description="Retrieve content for asking user questions.")
        # d_retrieve_content = caller.register_for_llm({
        #     description="Retrieve content for asking user questions.", api_style="function"
        # })(retrieve_content)
        
    return assistant