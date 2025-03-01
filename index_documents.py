from typing import List, Dict, Any, Optional
import os
import json
import logging
from datetime import datetime
from pathlib import Path
import argparse
from tqdm import tqdm
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        """Initialize the document processor with necessary clients and configurations"""
        # Load environment variables
        load_dotenv()
        
        # Validate environment variables
        self._validate_env_vars()
        
        # Initialize clients
        self.openai_client = OpenAI()
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_SERVICE_KEY", "")
        )
        
        # Configurations
        self.embedding_model = "text-embedding-ada-002"
        self.chunk_size = 1000
        self.chunk_overlap = 200
        
        logger.info("DocumentProcessor initialized successfully")
    
    def _validate_env_vars(self) -> None:
        """Validate if all required environment variables are present"""
        required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "OPENAI_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")
    
    def _read_markdown_files(self, framework: str) -> List[Dict[str, Any]]:
        """Read all markdown files for a specific framework"""
        documents = []
        output_dir = Path(__file__).parent / "output" / framework
        
        # Get the most recent date directory
        try:
            date_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
            if not date_dirs:
                raise ValueError(f"No date directories found for framework {framework}")
            
            latest_dir = max(date_dirs, key=lambda x: x.name)
            logger.info(f"Processing files from directory: {latest_dir}")
            
            # Read all markdown files
            for file_path in latest_dir.glob("*.md"):
                try:
                    # Read markdown content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Read corresponding metadata
                    meta_path = file_path.with_name(f"{file_path.stem}_meta.json")
                    if meta_path.exists():
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    else:
                        metadata = {}
                    
                    # Extract title from metadata or filename
                    title = metadata.get('title', file_path.stem.replace('_', ' ').title())
                    
                    # Create document object
                    documents.append({
                        "content": content,
                        "url": metadata.get("url", ""),
                        "title": title,
                        "metadata": {
                            "framework": framework,
                            "file_path": str(file_path),
                            "crawled_at": metadata.get("timestamp", datetime.now().isoformat()),
                            **metadata  # Include all other metadata
                        }
                    })
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    continue
            
            return documents
        except Exception as e:
            logger.error(f"Error reading documents for framework {framework}: {e}")
            return []
    
    def _chunk_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split document into smaller chunks with overlap"""
        content = document["content"]
        chunks = []
        
        # Split into paragraphs first
        paragraphs = content.split("\n\n")
        current_chunk = ""
        chunk_number = 0
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= self.chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    # Create chunk with metadata
                    chunks.append({
                        "url": document["url"],
                        "chunk_number": chunk_number,
                        "title": document["title"],
                        "content": current_chunk.strip(),
                        "summary": current_chunk[:200] + "...",  # Simple summary
                        "metadata": document["metadata"]
                    })
                    chunk_number += 1
                
                # Start new chunk with overlap
                words = current_chunk.split()
                overlap_text = " ".join(words[-self.chunk_overlap:]) if words else ""
                current_chunk = overlap_text + "\n\n" + paragraph + "\n\n"
        
        # Add the last chunk
        if current_chunk:
            chunks.append({
                "url": document["url"],
                "chunk_number": chunk_number,
                "title": document["title"],
                "content": current_chunk.strip(),
                "summary": current_chunk[:200] + "...",  # Simple summary
                "metadata": document["metadata"]
            })
        
        return chunks
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a text using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def _store_in_supabase(self, chunks: List[Dict[str, Any]], framework: str):
        """Store chunks and their embeddings in Supabase"""
        try:
            # First, delete existing documents for this framework
            self.supabase.table("site_pages").delete().eq("metadata->>framework", framework).execute()
            logger.info(f"Deleted existing documents for framework: {framework}")
            
            # Insert new chunks in batches
            batch_size = 50
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                
                # Generate embeddings for the batch
                for chunk in batch:
                    chunk["embedding"] = self._generate_embedding(chunk["content"])
                
                # Insert into Supabase
                self.supabase.table("site_pages").insert(batch).execute()
                
                logger.info(f"Inserted batch {i//batch_size + 1} of {len(chunks)//batch_size + 1}")
        
        except Exception as e:
            logger.error(f"Error storing documents in Supabase: {e}")
            raise
    
    def process_framework(self, framework: str):
        """Process all documents for a specific framework"""
        try:
            logger.info(f"Starting processing for framework: {framework}")
            
            # Read documents
            documents = self._read_markdown_files(framework)
            if not documents:
                logger.warning(f"No documents found for framework: {framework}")
                return
            
            logger.info(f"Found {len(documents)} documents")
            
            # Process chunks
            all_chunks = []
            for doc in tqdm(documents, desc="Chunking documents"):
                chunks = self._chunk_document(doc)
                all_chunks.extend(chunks)
            
            logger.info(f"Generated {len(all_chunks)} chunks")
            
            # Store in Supabase
            self._store_in_supabase(all_chunks, framework)
            
            logger.info(f"Successfully processed framework: {framework}")
            
        except Exception as e:
            logger.error(f"Error processing framework {framework}: {e}")
            raise

    def check_stored_documents(self, framework: str):
        """Check how many documents are stored for a framework"""
        try:
            result = self.supabase.table("site_pages")\
                .select("id", "url", "title", "chunk_number")\
                .eq("metadata->>framework", framework)\
                .execute()
            
            if result.data:
                logger.info(f"Found {len(result.data)} chunks for framework {framework}")
                logger.info(f"Sample URLs:")
                for doc in result.data[:5]:  # Show first 5 documents
                    logger.info(f"- {doc['url']} (Chunk {doc['chunk_number']})")
            else:
                logger.warning(f"No documents found for framework {framework}")
            
            return len(result.data)
        except Exception as e:
            logger.error(f"Error checking documents: {e}")
            return 0

def main():
    parser = argparse.ArgumentParser(description='Index documents for RAG system')
    parser.add_argument('--framework', help='Framework to process (if not specified, will process all)')
    parser.add_argument('--check', action='store_true', help='Check stored documents without processing')
    args = parser.parse_args()
    
    processor = DocumentProcessor()
    
    if args.check:
        if args.framework:
            processor.check_stored_documents(args.framework)
        else:
            output_dir = Path(__file__).parent / "output"
            frameworks = [d.name for d in output_dir.iterdir() if d.is_dir()]
            for framework in frameworks:
                processor.check_stored_documents(framework)
        return
    
    if args.framework:
        # Process specific framework
        processor.process_framework(args.framework)
        # Check after processing
        processor.check_stored_documents(args.framework)
    else:
        # Process all frameworks that have documents
        output_dir = Path(__file__).parent / "output"
        frameworks = [d.name for d in output_dir.iterdir() if d.is_dir()]
        
        for framework in frameworks:
            try:
                processor.process_framework(framework)
                processor.check_stored_documents(framework)
            except Exception as e:
                logger.error(f"Failed to process framework {framework}: {e}")
                continue

if __name__ == "__main__":
    main() 