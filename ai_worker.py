#!/usr/bin/env python3
"""
AI Worker - Handles document processing, indexing, and query processing
Equivalent to DARKBO's ai_worker.py
"""

import os
import json
import hashlib
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import numpy as np

try:
    import openai
    from sentence_transformers import SentenceTransformer
    import faiss
    from docx import Document
    import PyPDF2
    import chardet
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"⚠️  Missing dependency: {e}")
    print("Run: pip install -r requirements.txt")
    exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIWorker:
    """AI Worker for document processing and query handling"""
    
    def __init__(self, data_dir: str = "./data", openai_api_key: str = None):
        self.data_dir = Path(data_dir)
        self.indexes_dir = self.data_dir / "indexes"
        self.indexes_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up OpenAI
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        
        # Initialize embedding model
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("✅ Loaded sentence transformer model")
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            self.embedding_model = None
        
        # Vector index
        self.vector_index = None
        self.document_store = {}
        
    def extract_text_from_file(self, file_path: Path) -> str:
        """Extract text content from various file formats"""
        try:
            file_ext = file_path.suffix.lower()
            
            if file_ext == '.txt':
                # Detect encoding
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                    encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
                
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            
            elif file_ext == '.docx':
                doc = Document(file_path)
                text = []
                for paragraph in doc.paragraphs:
                    text.append(paragraph.text)
                return '\n'.join(text)
            
            elif file_ext == '.pdf':
                text = []
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    for page in pdf_reader.pages:
                        text.append(page.extract_text())
                return '\n'.join(text)
            
            elif file_ext in ['.html', '.htm']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f.read(), 'html.parser')
                    return soup.get_text()
            
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return ""
                
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks for better retrieval"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            if end > len(text):
                end = len(text)
            
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > start + chunk_size // 2:
                    chunk = text[start:start + break_point + 1]
                    end = start + break_point + 1
            
            chunks.append(chunk.strip())
            start = end - overlap
            
        return [chunk for chunk in chunks if chunk.strip()]
    
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for text chunks"""
        if not self.embedding_model:
            logger.error("Embedding model not available")
            return np.array([])
        
        try:
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return np.array([])
    
    def build_index_for_project(self, project_id: str) -> bool:
        """Build or rebuild the vector index for a project"""
        logger.info(f"🔨 Building index for project: {project_id}")
        
        project_dir = self.data_dir / project_id
        if not project_dir.exists():
            logger.error(f"Project directory not found: {project_dir}")
            return False
        
        # Collect all documents and content
        documents = []
        embeddings_list = []
        doc_id = 0
        
        # Process FAQs
        faqs_dir = project_dir / "faqs"
        if faqs_dir.exists():
            for faq_file in faqs_dir.glob("*.json"):
                try:
                    with open(faq_file, 'r', encoding='utf-8') as f:
                        faq = json.load(f)
                    
                    text = f"Q: {faq.get('question', '')}\nA: {faq.get('answer', '')}"
                    chunks = self.chunk_text(text)
                    
                    for chunk in chunks:
                        documents.append({
                            'id': doc_id,
                            'type': 'faq',
                            'source_file': str(faq_file),
                            'project_id': project_id,
                            'title': faq.get('question', ''),
                            'content': chunk,
                            'metadata': faq
                        })
                        doc_id += 1
                        
                except Exception as e:
                    logger.error(f"Error processing FAQ {faq_file}: {e}")
        
        # Process KB articles
        kb_dir = project_dir / "kb"
        if kb_dir.exists():
            for kb_file in kb_dir.glob("*.json"):
                try:
                    with open(kb_file, 'r', encoding='utf-8') as f:
                        kb = json.load(f)
                    
                    text = f"Title: {kb.get('title', '')}\nContent: {kb.get('content', '')}"
                    chunks = self.chunk_text(text)
                    
                    for chunk in chunks:
                        documents.append({
                            'id': doc_id,
                            'type': 'kb',
                            'source_file': str(kb_file),
                            'project_id': project_id,
                            'title': kb.get('title', ''),
                            'content': chunk,
                            'metadata': kb
                        })
                        doc_id += 1
                        
                except Exception as e:
                    logger.error(f"Error processing KB article {kb_file}: {e}")
        
        # Process ingested files
        ingest_dir = project_dir / "ingest"
        if ingest_dir.exists():
            for file_path in ingest_dir.iterdir():
                if file_path.is_file():
                    try:
                        text = self.extract_text_from_file(file_path)
                        if text.strip():
                            chunks = self.chunk_text(text)
                            
                            for chunk in chunks:
                                documents.append({
                                    'id': doc_id,
                                    'type': 'document',
                                    'source_file': str(file_path),
                                    'project_id': project_id,
                                    'title': file_path.name,
                                    'content': chunk,
                                    'metadata': {'filename': file_path.name}
                                })
                                doc_id += 1
                                
                    except Exception as e:
                        logger.error(f"Error processing document {file_path}: {e}")
        
        if not documents:
            logger.warning(f"No documents found for project {project_id}")
            return False
        
        # Generate embeddings
        texts = [doc['content'] for doc in documents]
        embeddings = self.generate_embeddings(texts)
        
        if embeddings.size == 0:
            logger.error("Failed to generate embeddings")
            return False
        
        # Build FAISS index
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        index.add(embeddings)
        
        # Save index and document store
        index_file = self.indexes_dir / f"{project_id}.index"
        docs_file = self.indexes_dir / f"{project_id}.docs"
        
        faiss.write_index(index, str(index_file))
        
        with open(docs_file, 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Built index for {project_id}: {len(documents)} chunks, {dimension}D embeddings")
        return True
    
    def load_project_index(self, project_id: str) -> bool:
        """Load the vector index for a project"""
        index_file = self.indexes_dir / f"{project_id}.index"
        docs_file = self.indexes_dir / f"{project_id}.docs"
        
        if not index_file.exists() or not docs_file.exists():
            logger.warning(f"Index not found for project {project_id}")
            return False
        
        try:
            self.vector_index = faiss.read_index(str(index_file))
            
            with open(docs_file, 'r', encoding='utf-8') as f:
                self.document_store = {doc['id']: doc for doc in json.load(f)}
            
            logger.info(f"✅ Loaded index for {project_id}: {len(self.document_store)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Error loading index for {project_id}: {e}")
            return False
    
    def search_documents(self, query: str, project_id: str = None, top_k: int = 5) -> List[Dict]:
        """Search for relevant documents using vector similarity"""
        if not self.vector_index or not self.document_store:
            if project_id:
                if not self.load_project_index(project_id):
                    return []
            else:
                return []
        
        try:
            # Generate query embedding
            query_embedding = self.generate_embeddings([query])
            if query_embedding.size == 0:
                return []
            
            # Normalize for cosine similarity
            faiss.normalize_L2(query_embedding)
            
            # Search
            scores, indices = self.vector_index.search(query_embedding, top_k)
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx in self.document_store:
                    doc = self.document_store[idx].copy()
                    doc['similarity_score'] = float(score)
                    results.append(doc)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    def query_with_ai(self, query: str, context_docs: List[Dict], project_id: str = None) -> Dict:
        """Generate AI response using OpenAI with retrieved context"""
        if not self.openai_api_key:
            return {
                "answer": "AI query processing requires OpenAI API key to be configured.",
                "sources": context_docs[:3]
            }
        
        try:
            # Prepare context from retrieved documents
            context_texts = []
            sources = []
            
            for doc in context_docs[:5]:  # Use top 5 results
                context_texts.append(f"Source: {doc['title']}\nContent: {doc['content']}")
                sources.append({
                    'title': doc['title'],
                    'type': doc['type'],
                    'source_file': doc.get('source_file', ''),
                    'similarity_score': doc.get('similarity_score', 0)
                })
            
            if not context_texts:
                return {
                    "answer": "I couldn't find any relevant information to answer your question.",
                    "sources": []
                }
            
            context = "\n\n".join(context_texts)
            
            # Create prompt
            prompt = f"""Based on the following context information, please answer the user's question. If the context doesn't contain enough information to answer the question, say so clearly.

Context:
{context}

Question: {query}

Please provide a helpful and accurate answer based on the context provided."""

            # Call OpenAI API
            client = openai.OpenAI(api_key=self.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful knowledge base assistant. Answer questions based on the provided context."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content.strip()
            
            return {
                "answer": answer,
                "sources": sources
            }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return {
                "answer": f"Error generating response: {str(e)}",
                "sources": context_docs[:3]
            }
    
    def process_query(self, query: str, project_id: str = None) -> Dict:
        """Main query processing function"""
        logger.info(f"🔍 Processing query: {query}")
        
        # Search for relevant documents
        relevant_docs = self.search_documents(query, project_id)
        
        if not relevant_docs:
            return {
                "answer": "I couldn't find any relevant information to answer your question. Please try rephrasing your query or check if the knowledge base contains information about this topic.",
                "sources": []
            }
        
        # Generate AI response with context
        result = self.query_with_ai(query, relevant_docs, project_id)
        
        logger.info(f"✅ Query processed: {len(result['sources'])} sources used")
        return result

def initialize_all_indexes(data_dir: str = "./data"):
    """Initialize indexes for all projects"""
    worker = AIWorker(data_dir)
    
    # Read project mapping
    proj_mapping_file = Path(data_dir) / "proj_mapping.txt"
    if not proj_mapping_file.exists():
        logger.error("Project mapping file not found")
        return False
    
    projects = []
    for line in proj_mapping_file.read_text(encoding='utf-8').splitlines():
        if line.strip():
            parts = line.split('|', 2)
            if len(parts) == 3:
                project_id, name, active = parts
                if active == '1':  # Only process active projects
                    projects.append(project_id)
    
    logger.info(f"🚀 Initializing indexes for {len(projects)} projects")
    
    success_count = 0
    for project_id in projects:
        if worker.build_index_for_project(project_id):
            success_count += 1
        time.sleep(1)  # Brief pause between projects
    
    logger.info(f"✅ Initialization complete: {success_count}/{len(projects)} projects indexed")
    return success_count == len(projects)

if __name__ == "__main__":
    # Test the AI worker
    worker = AIWorker()
    
    # Build index for a test project
    success = worker.build_index_for_project("tech-support")
    if success:
        print("✅ Index built successfully")
        
        # Test query
        result = worker.process_query("How do I reset my password?", "tech-support")
        print(f"Query result: {result}")
    else:
        print("❌ Failed to build index")