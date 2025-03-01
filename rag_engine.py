from typing import List, Dict, Any, Optional
import os
import logging
import time
from openai import OpenAI
from supabase import create_client, Client
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        """Initialize the RAG engine with the necessary configurations"""
        # Load environment variables
        load_dotenv()
        
        # Validate required environment variables
        self._validate_env_vars()
        
        # Initialize clients
        self.openai_client = OpenAI()
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_SERVICE_KEY", "")
        )
        
        # Configurations
        self.embedding_model = "text-embedding-ada-002"
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4")
        
        logger.info("RAGEngine initialized successfully")
    
    def _validate_env_vars(self) -> None:
        """Validate if all required environment variables are present"""
        required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "OPENAI_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a text using OpenAI
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            List of floats representing the embedding
            
        Raises:
            Exception: If there's an error in the embedding generation
        """
        try:
            logger.debug(f"Generating embedding for text of size {len(text)}")
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise Exception(f"Error generating embedding: {e}")

    def retrieve_documents(self, 
                         query: str, 
                         framework: str, 
                         top_k: int = 8) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents based on the query
        
        Args:
            query: User question
            framework: Framework name
            top_k: Maximum number of documents to return
            
        Returns:
            List of relevant documents
        """
        try:
            logger.info(f"Searching documents for framework: {framework}")
            query_embedding = self._generate_embedding(query)
            
            result = self.supabase.rpc(
                'match_documents',
                {
                    'query_embedding': query_embedding,
                    'match_count': top_k,
                    'framework_filter': framework.lower()
                }
            ).execute()
            
            logger.info(f"Found {len(result.data)} documents")
            return result.data
        except Exception as e:
            logger.error(f"Error in document retrieval: {e}")
            raise Exception(f"Error in document retrieval: {e}")

    def _prepare_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Prepare the context from the retrieved chunks with improved formatting"""
        formatted_chunks = []
        for chunk in chunks:
            formatted_chunk = (
                f"Section: {chunk.get('title', 'No title')}\n"
                f"URL: {chunk['url']}\n"
                f"Content:\n{chunk['content']}\n"
                f"{'=' * 50}"
            )
            formatted_chunks.append(formatted_chunk)
        
        return "\n\n".join(formatted_chunks)

    def _get_system_prompt(self, framework: str) -> str:
        """Returns the system prompt specific to each framework"""
        system_prompts = {
            'crawl4ai': """You are an expert on Crawl4AI, specialized in asynchronous web crawling.
            Use the provided context to answer questions about configuration, strategies, and optimizations.""",
            
            'pydantic': """You are an expert on Pydantic AI, specialized in data validation for AI.
            Use the provided context to answer questions about models, validations, and integrations.""",

            'agno': """You are an expert on Agno, specialized in web development.
            Use the provided context to answer questions about configuration, development, and best practices.""",
            
            'mcp': """You are an expert on Model Context Protocol (MCP), specialized in model context management and LLM interactions.
            
            Key areas of expertise:
            1. Protocol specifications and architecture
            2. Client-server implementations
            3. Tool definitions and integrations
            4. Resource management and context handling
            5. Transport layer configurations
            6. Debugging and inspection tools
            
            When answering:
            - Focus on practical implementation details
            - Provide code examples when relevant
            - Reference specific MCP concepts and components
            - Explain how features integrate with LLM systems
            - Highlight best practices and common pitfalls
            
            Use the provided context to give accurate, implementation-focused answers."""
        }
        return system_prompts.get(framework, "You are a specialized assistant for technical documentation.")

    def generate_response(self, 
                         query: str, 
                         chunks: List[Dict[str, Any]], 
                         framework: str) -> str:
        """
        Generate response based on retrieved documents with improved context handling
        
        Args:
            query: User question
            chunks: List of relevant documents
            framework: Framework name
            
        Returns:
            Generated response
        """
        try:
            context = self._prepare_context(chunks)
            system_prompt = self._get_system_prompt(framework)
            
            # Improved prompt structure for better context utilization
            user_prompt = f"""Based on the following documentation sections, answer the question below.
            If the answer cannot be fully derived from the provided context, say so.
            
            Documentation Sections:
            {context}
            
            Question: {query}
            
            Please provide a clear, structured answer with:
            1. Direct response to the question
            2. Relevant code examples (if applicable)
            3. Links to related documentation (if available)"""
            
            logger.info("Generating response with LLM")
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7  # Slightly creative but still focused
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in response generation: {e}")
            raise Exception(f"Error in response generation: {e}")

    def format_sources(self, chunks: List[Dict[str, Any]]) -> str:
        """Format the sources of the retrieved documents"""
        sources = []
        for chunk in chunks:
            url = chunk.get('url', '')
            title = chunk.get('title', 'No title')
            sources.append(f"- [{title}]({url})")
        
        return "\n".join(sources)

    def query(self, question: str, framework: str) -> Dict[str, Optional[str]]:
        """
        Main method that executes the complete RAG pipeline
        
        Args:
            question: User question
            framework: Framework name
            
        Returns:
            Dictionary containing answer, sources and possible error
        """
        try:
            logger.info(f"Starting query for framework {framework}")
            chunks = self.retrieve_documents(question, framework)
            
            if not chunks:
                logger.warning("No relevant documents found")
                return {
                    "answer": "No relevant documents were found. Please try rephrasing your question or ask about a different topic.",
                    "sources": "",
                    "error": None
                }
            
            response = self.generate_response(question, chunks, framework)
            sources = self.format_sources(chunks)
            
            logger.info("Query completed successfully")
            return {
                "answer": response,
                "sources": sources,
                "error": None
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error during query: {error_msg}")
            return {
                "answer": "",
                "sources": "",
                "error": str(e)
            }