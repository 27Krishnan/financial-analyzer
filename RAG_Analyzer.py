"""
RAG-based Financial Document Analyzer
PDF → Text Extraction → Chunking → Embeddings → Vector DB → LLM → Answer
"""

import os
import re
import json
import hashlib
import pdfplumber
import requests
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
import pickle

# ============================================================================
# CONFIGURATION
# ============================================================================
API_KEY = os.getenv("NVIDIA_API_KEY", "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")
NVIDIA_EMBEDDINGS_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Chunking settings
CHUNK_SIZE = 500  # Characters per chunk
CHUNK_OVERLAP = 50  # Overlap between chunks

# Vector DB storage
VECTOR_DB_PATH = os.path.join(os.path.dirname(__file__), "vector_db")


# ============================================================================
# DATA CLASSES
# ============================================================================
@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    id: str
    text: str
    page: int
    start_idx: int
    end_idx: int
    embedding: Optional[np.ndarray] = None
    similarity: Optional[float] = None


@dataclass
class SearchResult:
    """Search result with chunk and score."""
    chunk: Chunk
    score: float
    rank: int


# ============================================================================
# TEXT EXTRACTOR
# ============================================================================
class PDFTextExtractor:
    """Extract text from PDF with structure preservation."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        
    def extract(self) -> Dict:
        """Extract text with page-wise structure."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"PDF not found: {self.file_path}")
        
        pages = []
        full_text = ""
        
        with pdfplumber.open(self.file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                
                # Extract tables separately
                tables = []
                for table in page.extract_tables():
                    if table:
                        table_text = self._table_to_text(table)
                        if table_text:
                            tables.append(table_text)
                
                pages.append({
                    "page": page_num,
                    "text": text,
                    "tables": tables
                })
                
                full_text += f"\n[PAGE {page_num}]\n{text}"
                for table in tables:
                    full_text += f"\n[TABLE]\n{table}"
        
        return {
            "pages": pages,
            "full_text": full_text,
            "total_pages": len(pages)
        }
    
    def _table_to_text(self, table: list) -> str:
        """Convert table to text representation."""
        rows = []
        for row in table:
            if row:
                cells = [str(cell).strip() if cell else "" for cell in row]
                rows.append(" | ".join(cells))
        return "\n".join(rows)


# ============================================================================
# TEXT CHUNKER
# ============================================================================
class TextChunker:
    """Split text into overlapping chunks with metadata."""
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap
        
    def chunk(self, pages: List[Dict]) -> List[Chunk]:
        """Create chunks from page-wise text."""
        chunks = []
        
        for page_data in pages:
            page_num = page_data["page"]
            text = page_data["text"]
            tables = page_data.get("tables", [])
            
            # Chunk main text
            text_chunks = self._split_text(text, page_num)
            chunks.extend(text_chunks)
            
            # Chunk tables separately
            for table_idx, table in enumerate(tables):
                table_chunks = self._split_text(
                    f"[TABLE {table_idx + 1}]\n{table}", 
                    page_num,
                    prefix="TABLE"
                )
                chunks.extend(table_chunks)
        
        return chunks
    
    def _split_text(self, text: str, page: int, prefix: str = "TEXT") -> List[Chunk]:
        """Split text into overlapping chunks."""
        chunks = []
        
        # Clean text
        text = re.sub(r'\n\s*\n', '\n\n', text).strip()
        
        if len(text) < self.chunk_size:
            # Small text - single chunk
            chunk = Chunk(
                id=self._generate_id(prefix, page, 0),
                text=text,
                page=page,
                start_idx=0,
                end_idx=len(text)
            )
            chunks.append(chunk)
            return chunks
        
        # Split into overlapping chunks
        start = 0
        chunk_idx = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Try to break at sentence/word boundary
            if end < len(text):
                # Find last sentence boundary
                last_period = text.rfind('.', start, end)
                last_newline = text.rfind('\n', start, end)
                last_space = text.rfind(' ', start, end)
                
                boundary = max(last_period, last_newline, last_space)
                if boundary > start + self.chunk_size // 2:
                    end = boundary + 1
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunk = Chunk(
                    id=self._generate_id(prefix, page, chunk_idx),
                    text=chunk_text,
                    page=page,
                    start_idx=start,
                    end_idx=end
                )
                chunks.append(chunk)
                chunk_idx += 1
            
            # Move start with overlap
            start = end - self.overlap
            if start < 0:
                start = end
        
        return chunks
    
    def _generate_id(self, prefix: str, page: int, idx: int) -> str:
        """Generate unique chunk ID."""
        text = f"{prefix}-{page}-{idx}"
        return hashlib.md5(text.encode()).hexdigest()[:16]


# ============================================================================
# EMBEDDINGS (NVIDIA API)
# ============================================================================
class EmbeddingGenerator:
    """Generate embeddings using NVIDIA API."""
    
    def __init__(self, api_key: str = API_KEY):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.model = "nvidia/nv-embedqa-e5-v5"
        
    def generate(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        if not texts:
            return np.array([])
        
        # Batch processing (max 100 per batch)
        all_embeddings = []
        
        for i in range(0, len(texts), 100):
            batch = texts[i:i+100]
            embeddings = self._generate_batch(batch)
            all_embeddings.extend(embeddings)
        
        return np.array(all_embeddings)
    
    def _generate_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for a batch of texts."""
        payload = {
            "model": self.model,
            "input": texts,
            "input_type": "passage",
            "encoding_format": "float"
        }
        
        try:
            response = requests.post(
                NVIDIA_EMBEDDINGS_URL,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            embeddings = [np.array(item["embedding"]) for item in data["data"]]
            
            # Sort by original index
            embeddings = [e for _, e in sorted(zip(
                [item["index"] for item in data["data"]],
                embeddings
            ))]
            
            return embeddings
            
        except Exception as e:
            print(f"Embedding error: {e}")
            # Return zero embeddings as fallback
            dim = 1024  # E5 embedding dimension
            return [np.zeros(dim) for _ in texts]
    
    def generate_query(self, query: str) -> np.ndarray:
        """Generate embedding for a query."""
        payload = {
            "model": self.model,
            "input": [query],
            "input_type": "query",
            "encoding_format": "float"
        }
        
        try:
            response = requests.post(
                NVIDIA_EMBEDDINGS_URL,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            return np.array(data["data"][0]["embedding"])
            
        except Exception as e:
            print(f"Query embedding error: {e}")
            return np.zeros(1024)


# ============================================================================
# VECTOR DATABASE (FAISS-like with NumPy)
# ============================================================================
class VectorDatabase:
    """Simple vector database with similarity search."""
    
    def __init__(self, db_path: str = VECTOR_DB_PATH):
        self.db_path = db_path
        self.chunks: List[Chunk] = []
        self.embeddings: Optional[np.ndarray] = None
        self.index_map: Dict[str, int] = {}
        
        os.makedirs(db_path, exist_ok=True)
    
    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray):
        """Add chunks with embeddings to the database."""
        start_idx = len(self.chunks)
        
        for i, chunk in enumerate(chunks):
            chunk.embedding = embeddings[i]
            self.index_map[chunk.id] = start_idx + i
            self.chunks.append(chunk)
        
        # Update embeddings matrix
        if self.embeddings is None:
            self.embeddings = embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, embeddings])
        
        # Normalize for cosine similarity
        self._normalize()
    
    def _normalize(self):
        """Normalize embeddings for cosine similarity."""
        if self.embeddings is not None and len(self.embeddings) > 0:
            norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1  # Avoid division by zero
            self.embeddings = self.embeddings / norms
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[SearchResult]:
        """Search for similar chunks."""
        if self.embeddings is None or len(self.chunks) == 0:
            return []
        
        # Normalize query
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm
        
        # Calculate cosine similarity
        similarities = np.dot(self.embeddings, query_embedding)
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for rank, idx in enumerate(top_indices):
            if similarities[idx] > 0:  # Only positive similarities
                results.append(SearchResult(
                    chunk=self.chunks[idx],
                    score=float(similarities[idx]),
                    rank=rank + 1
                ))
        
        return results
    
    def save(self, filename: str = "vector_db.pkl"):
        """Save database to disk."""
        data = {
            "chunks": self.chunks,
            "embeddings": self.embeddings,
            "index_map": self.index_map
        }
        
        # Don't save embeddings in chunks (duplicate)
        for chunk in data["chunks"]:
            chunk.embedding = None
        
        filepath = os.path.join(self.db_path, filename)
        with open(filepath, "wb") as f:
            pickle.dump(data, f)
        
        # Save embeddings separately (numpy format)
        if self.embeddings is not None:
            np.save(os.path.join(self.db_path, "embeddings.npy"), self.embeddings)
    
    def load(self, filename: str = "vector_db.pkl") -> bool:
        """Load database from disk."""
        filepath = os.path.join(self.db_path, filename)
        
        if not os.path.exists(filepath):
            return False
        
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        
        self.chunks = data["chunks"]
        self.index_map = data["index_map"]
        
        # Load embeddings
        emb_path = os.path.join(self.db_path, "embeddings.npy")
        if os.path.exists(emb_path):
            self.embeddings = np.load(emb_path)
        
        return True
    
    def clear(self):
        """Clear the database."""
        self.chunks = []
        self.embeddings = None
        self.index_map = {}


# ============================================================================
# LLM (NVIDIA API)
# ============================================================================
class LLMGenerator:
    """Generate answers using NVIDIA LLM API."""
    
    def __init__(self, api_key: str = API_KEY):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.model = "meta/llama3-70b-instruct"
    
    def generate(self, query: str, context: str) -> str:
        """Generate answer based on query and context."""
        prompt = f"""You are an expert financial analyst. Use the following context from a financial document to answer the query.

CONTEXT (from document):
{context}

QUERY: {query}

Provide a clear, accurate answer based ONLY on the context provided. If the context doesn't contain enough information, say so clearly. Include page numbers when referencing specific information."""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an expert financial analyst specializing in Indian company reports."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }
        
        try:
            response = requests.post(
                NVIDIA_CHAT_URL,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            return data["choices"][0]["message"]["content"]
            
        except Exception as e:
            return f"Error generating answer: {str(e)}"


# ============================================================================
# RAG ANALYZER (Main Class)
# ============================================================================
class RAGAnalyzer:
    """Complete RAG pipeline for financial document analysis."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pdf_name = os.path.basename(pdf_path)
        
        # Initialize components
        self.extractor = PDFTextExtractor(pdf_path)
        self.chunker = TextChunker()
        self.embedder = EmbeddingGenerator()
        self.vector_db = VectorDatabase()
        self.llm = LLMGenerator()
        
        # Processing state
        self.is_processed = False
    
    def process(self, use_cache: bool = True) -> Dict:
        """Process the PDF through the complete RAG pipeline."""
        cache_file = f"rag_cache_{hashlib.md5(self.pdf_path.encode()).hexdigest()[:16]}.pkl"
        
        # Try to load from cache
        if use_cache and self.vector_db.load(cache_file):
            print(f"✓ Loaded cached vector database ({len(self.vector_db.chunks)} chunks)")
            self.is_processed = True
            return {
                "status": "loaded_from_cache",
                "chunks": len(self.vector_db.chunks)
            }
        
        print(f"\n{'='*60}")
        print(f"Processing: {self.pdf_name}")
        print(f"{'='*60}\n")
        
        # Step 1: Extract text
        print("Step 1/5: Extracting text from PDF...")
        extracted = self.extractor.extract()
        print(f"  ✓ Extracted {extracted['total_pages']} pages")
        
        # Step 2: Chunk text
        print("\nStep 2/5: Chunking text...")
        chunks = self.chunker.chunk(extracted["pages"])
        print(f"  ✓ Created {len(chunks)} chunks")
        
        # Step 3: Generate embeddings
        print("\nStep 3/5: Generating embeddings...")
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedder.generate(texts)
        print(f"  ✓ Generated {len(embeddings)} embeddings")
        
        # Step 4: Store in vector DB
        print("\nStep 4/5: Storing in vector database...")
        self.vector_db.add_chunks(chunks, embeddings)
        print(f"  ✓ Stored {len(self.vector_db.chunks)} vectors")
        
        # Step 5: Save cache
        print("\nStep 5/5: Saving cache...")
        self.vector_db.save(cache_file)
        print(f"  ✓ Cache saved")
        
        self.is_processed = True
        
        return {
            "status": "processed",
            "total_pages": extracted["total_pages"],
            "total_chunks": len(chunks),
            "embedding_dim": embeddings.shape[1] if len(embeddings) > 0 else 0
        }
    
    def query(self, question: str, top_k: int = 5) -> Dict:
        """Query the document using RAG."""
        if not self.is_processed:
            return {"error": "Document not processed. Call process() first."}
        
        print(f"\n{'='*60}")
        print(f"Query: {question}")
        print(f"{'='*60}\n")
        
        # Step 1: Generate query embedding
        print("Step 1/3: Generating query embedding...")
        query_embedding = self.embedder.generate_query(question)
        
        # Step 2: Search vector DB
        print("Step 2/3: Searching vector database...")
        results = self.vector_db.search(query_embedding, top_k=top_k)
        print(f"  ✓ Found {len(results)} relevant chunks")
        
        # Step 3: Build context
        context = self._build_context(results)
        
        # Step 4: Generate answer
        print("Step 3/3: Generating answer with LLM...")
        answer = self.llm.generate(question, context)
        
        return {
            "query": question,
            "answer": answer,
            "sources": [
                {
                    "page": r.chunk.page,
                    "score": round(r.score, 3),
                    "text": r.chunk.text[:200] + "..." if len(r.chunk.text) > 200 else r.chunk.text
                }
                for r in results
            ],
            "context": context
        }
    
    def _build_context(self, results: List[SearchResult]) -> str:
        """Build context from search results."""
        context_parts = []
        
        for result in results:
            chunk = result.chunk
            context_parts.append(
                f"[Page {chunk.page}] (Relevance: {result.score:.3f})\n{chunk.text}"
            )
        
        return "\n\n" + "="*50 + "\n\n".join(context_parts)
    
    def interactive_mode(self):
        """Start interactive query mode."""
        print("\n" + "="*60)
        print("RAG Analyzer - Interactive Mode")
        print("="*60)
        print("Type your questions about the document.")
        print("Type 'exit' or 'quit' to stop.\n")
        
        while True:
            try:
                question = input("You: ").strip()
                
                if question.lower() in ['exit', 'quit', 'q']:
                    print("Goodbye!")
                    break
                
                if not question:
                    continue
                
                result = self.query(question)
                
                if "error" in result:
                    print(f"Error: {result['error']}")
                else:
                    print(f"\n🤖 Answer:\n{result['answer']}\n")
                    print("\n📚 Sources:")
                    for i, source in enumerate(result['sources'], 1):
                        print(f"\n{i}. Page {source['page']} (Score: {source['score']})")
                        print(f"   {source['text']}")
                    print()
                    
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {str(e)}")


# ============================================================================
# MAIN
# ============================================================================
def main():
    """Main entry point."""
    print("="*60)
    print("RAG-based Financial Document Analyzer")
    print("PDF → Text → Chunks → Embeddings → Vector DB → LLM → Answer")
    print("="*60)
    
    pdf_path = input("\nEnter PDF file path: ").strip().strip('"')
    
    if not os.path.exists(pdf_path):
        print(f"Error: File not found at {pdf_path}")
        return
    
    # Create analyzer
    analyzer = RAGAnalyzer(pdf_path)
    
    # Process document
    result = analyzer.process()
    
    if result["status"] == "processed":
        print(f"\n✅ Processing complete!")
        print(f"   Pages: {result.get('total_pages', 'N/A')}")
        print(f"   Chunks: {result.get('total_chunks', 'N/A')}")
        print(f"   Embedding Dim: {result.get('embedding_dim', 'N/A')}")
    
    # Start interactive mode
    analyzer.interactive_mode()


if __name__ == "__main__":
    main()
