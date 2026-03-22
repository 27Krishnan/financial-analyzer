"""
RAG-Based Document Intelligence Layer
PDF → Chunk → Embed → Store (FAISS) → Query → Answer + Evidence
"""

import os
import re
import json
import hashlib
import pickle
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import pdfplumber
import numpy as np
from tqdm import tqdm

# AI/ML imports (optional - will work without for lite version)
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"RAG libraries not available (lite mode): {e}")
    RAG_AVAILABLE = False
    # Create dummy class for lite mode
    class SentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass
    class faiss:
        class IndexFlatIP:
            def __init__(self, *args):
                pass
            def add(self, *args):
                pass
            def search(self, *args):
                return None, None
            @property
            def ntotal(self):
                return 0


@dataclass
class DocumentChunk:
    """Represents a chunk of document text with metadata."""
    chunk_id: str
    text: str
    page: int
    start_pos: int
    end_pos: int
    section: str = ""
    embedding: Optional[np.ndarray] = None


class RAGDocumentAnalyzer:
    """
    RAG-based document analyzer with semantic search.
    
    Pipeline:
    1. Load PDF → Extract text
    2. Chunk → Split into semantic chunks
    3. Embed → Generate embeddings using Sentence Transformers
    4. Store → Save in FAISS index
    5. Query → Retrieve relevant chunks + generate answer
    """
    
    def __init__(self, file_path: str, model_name: str = "all-MiniLM-L6-v2"):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.model_name = model_name
        
        # Document data
        self.chunks: List[DocumentChunk] = []
        self.full_text: List[Dict] = []  # [{page, text}]
        self.metadata = {}
        
        # RAG components
        self.model = None
        self.index = None
        self.chunk_embeddings = None
        
        # Cache directory
        self.cache_dir = os.path.join(os.path.dirname(file_path), 'rag_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        if RAG_AVAILABLE:
            self._load_model()
    
    def _load_model(self):
        """Load sentence transformer model."""
        try:
            print(f"  Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            print(f"  ✓ Model loaded successfully")
        except Exception as e:
            print(f"  ✗ Error loading model: {e}")
            self.model = None
    
    def _generate_chunk_id(self, text: str, page: int) -> str:
        """Generate unique chunk ID."""
        content = f"{page}:{text[:100]}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _extract_text_from_pdf(self):
        """Extract text from all pages of PDF."""
        print(f"  Extracting text from PDF: {self.file_path}")
        
        self.full_text = []
        
        try:
            with pdfplumber.open(self.file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        self.full_text.append({
                            'page': i + 1,
                            'text': text,
                            'tables': page.extract_tables()
                        })
            
            print(f"  ✓ Extracted text from {len(self.full_text)} pages")
        except Exception as e:
            print(f"  ✗ Error extracting text: {e}")
            raise
    
    def _chunk_text(self, chunk_size: int = 500, overlap: int = 50) -> List[DocumentChunk]:
        """
        Split document text into semantic chunks.
        
        Strategy:
        - Split by paragraphs first
        - Merge/split to target chunk_size
        - Maintain overlap for context
        """
        print(f"  Chunking text (size={chunk_size}, overlap={overlap})...")
        
        chunks = []
        chunk_count = 0
        
        for page_data in self.full_text:
            page_num = page_data['page']
            text = page_data['text']
            
            # Split by paragraphs
            paragraphs = re.split(r'\n\s*\n', text)
            
            current_chunk = ""
            current_start = 0
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                # If paragraph is larger than chunk_size, split by sentences
                if len(para) > chunk_size:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                            # Save current chunk
                            chunk = DocumentChunk(
                                chunk_id=self._generate_chunk_id(current_chunk, page_num),
                                text=current_chunk.strip(),
                                page=page_num,
                                start_pos=current_start,
                                end_pos=current_start + len(current_chunk),
                                section=self._detect_section(current_chunk)
                            )
                            chunks.append(chunk)
                            chunk_count += 1
                            
                            # Start new chunk with overlap
                            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else ""
                            current_chunk = overlap_text + " " + sentence
                            current_start = chunk.end_pos - overlap
                        else:
                            current_chunk += " " + sentence
                
                # Normal paragraph handling
                elif len(current_chunk) + len(para) > chunk_size and current_chunk:
                    # Save current chunk
                    chunk = DocumentChunk(
                        chunk_id=self._generate_chunk_id(current_chunk, page_num),
                        text=current_chunk.strip(),
                        page=page_num,
                        start_pos=current_start,
                        end_pos=current_start + len(current_chunk),
                        section=self._detect_section(current_chunk)
                    )
                    chunks.append(chunk)
                    chunk_count += 1
                    
                    # Start new chunk with overlap
                    overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else ""
                    current_chunk = overlap_text + " " + para
                    current_start = page_data['text'].find(para) - overlap
                else:
                    current_chunk += " " + para
            
            # Save last chunk
            if current_chunk.strip():
                chunk = DocumentChunk(
                    chunk_id=self._generate_chunk_id(current_chunk, page_num),
                    text=current_chunk.strip(),
                    page=page_num,
                    start_pos=current_start,
                    end_pos=current_start + len(current_chunk),
                    section=self._detect_section(current_chunk)
                )
                chunks.append(chunk)
                chunk_count += 1
        
        print(f"  ✓ Created {len(chunks)} chunks")
        self.chunks = chunks
        return chunks
    
    def _detect_section(self, text: str) -> str:
        """Detect which section of financial report this chunk belongs to."""
        text_lower = text[:200].lower()
        
        section_keywords = {
            'financial_statements': ['balance sheet', 'statement of assets', 'statement of liabilities'],
            'profit_loss': ['profit and loss', 'statement of profit', 'income statement', 'revenue from operations'],
            'cash_flow': ['cash flow', 'cash flow statement', 'net cash from'],
            'notes': ['notes to accounts', 'significant accounting', 'note'],
            'directors_report': ['directors report', 'board report', 'management discussion'],
            'auditors_report': ['auditors report', 'independent auditors', 'audit opinion'],
            'segment_info': ['segment reporting', 'business segment', 'geographical segment'],
            'share_capital': ['share capital', 'equity share', 'dividend per share'],
        }
        
        for section, keywords in section_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return section
        
        return 'general'
    
    def _create_embeddings(self, batch_size: int = 32):
        """Generate embeddings for all chunks using Sentence Transformers."""
        if not self.model:
            print("  ✗ Model not loaded, skipping embeddings")
            return False
        
        print(f"  Creating embeddings for {len(self.chunks)} chunks...")
        
        texts = [chunk.text for chunk in self.chunks]
        embeddings = []
        
        # Process in batches
        for i in tqdm(range(0, len(texts), batch_size), desc="Embedding"):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
            embeddings.append(batch_embeddings)
        
        embeddings = np.vstack(embeddings)
        
        # Normalize embeddings for cosine similarity
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        self.chunk_embeddings = embeddings
        print(f"  ✓ Created embeddings: {embeddings.shape}")
        return True
    
    def _create_faiss_index(self):
        """Create FAISS index for efficient similarity search."""
        if self.chunk_embeddings is None:
            print("  ✗ No embeddings to index")
            return False
        
        print("  Creating FAISS index...")
        
        dimension = self.chunk_embeddings.shape[1]
        
        # Use IndexFlatIP for cosine similarity (normalized vectors)
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(self.chunk_embeddings.astype('float32'))
        
        print(f"  ✓ FAISS index created with {self.index.ntotal} vectors")
        return True
    
    def build_index(self, chunk_size: int = 800, overlap: int = 100):
        """
        Complete pipeline: Extract → Chunk → Embed → Index
        
        Args:
            chunk_size: Target size for each chunk (characters) - larger = fewer chunks
            overlap: Overlap between consecutive chunks
        """
        print("\n" + "="*60)
        print("RAG Document Indexing Pipeline")
        print("="*60)
        
        # Step 1: Extract text
        self._extract_text_from_pdf()
        
        # Step 2: Chunk text
        self._chunk_text(chunk_size, overlap)
        
        # Step 3: Create embeddings (only if model loaded)
        if self.model:
            if not self._create_embeddings(batch_size=64):  # Larger batch = faster
                print("  ⚠ Skipping embedding creation")
            
            # Step 4: Create FAISS index
            if not self._create_faiss_index():
                print("  ⚠ Skipping FAISS index creation")
        else:
            print("  ⚠ Model not available, using keyword search only")
        
        # Step 5: Save cache
        self._save_cache()
        
        print("="*60)
        print(f"RAG Indexing Complete! ({len(self.chunks)} chunks)")
        print("="*60)
    
    def _save_cache(self):
        """Save processed data to cache."""
        cache_file = os.path.join(self.cache_dir, f"{hashlib.md5(self.file_path.encode()).hexdigest()[:16]}.pkl")
        
        cache_data = {
            'chunks': self.chunks,
            'full_text': self.full_text,
            'chunk_embeddings': self.chunk_embeddings,
            'metadata': {
                'file_name': self.file_name,
                'num_chunks': len(self.chunks),
                'num_pages': len(self.full_text)
            }
        }
        
        # Save embeddings separately (large)
        if self.chunk_embeddings is not None:
            emb_file = cache_file.replace('.pkl', '_embeddings.npy')
            np.save(emb_file, self.chunk_embeddings)
        
        # Save metadata
        meta_file = cache_file.replace('.pkl', '_meta.json')
        with open(meta_file, 'w') as f:
            json.dump(cache_data['metadata'], f, indent=2)
        
        print(f"  ✓ Cache saved to {self.cache_dir}")
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for relevant chunks using semantic similarity.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of (chunk, similarity_score) tuples
        """
        if self.index is None or self.model is None:
            # Fallback to keyword search
            return self._keyword_search(query, top_k)
        
        # Generate query embedding
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Search FAISS index
        scores, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.chunks):
                results.append((self.chunks[idx], float(score)))
        
        return results
    
    def _keyword_search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """Fallback keyword-based search."""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored_chunks = []
        
        for chunk in self.chunks:
            chunk_lower = chunk.text.lower()
            
            # Simple scoring: count matching words
            score = sum(1 for word in query_words if word in chunk_lower)
            
            # Boost for exact phrase match
            if query_lower in chunk_lower:
                score *= 2
            
            if score > 0:
                scored_chunks.append((chunk, score / len(query_words)))
        
        # Sort by score and return top_k
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]
    
    def query(self, question: str, top_k: int = 5) -> Dict:
        """
        Answer question using RAG pipeline.
        
        Args:
            question: User question
            top_k: Number of chunks to retrieve
        
        Returns:
            Dict with answer, evidence, confidence
        """
        print(f"\n  Query: {question}")
        
        # Step 1: Retrieve relevant chunks
        results = self.search(question, top_k)
        
        if not results:
            return {
                'answer': 'No relevant information found in the document.',
                'evidence': [],
                'confidence': 0.0,
                'pages': []
            }
        
        # Step 2: Extract answer from top chunks
        top_chunks = results[:3]  # Use top 3 for answer extraction
        evidence_chunks = results[:top_k]
        
        # Step 3: Generate answer (simple extraction-based)
        answer = self._extract_answer(question, top_chunks)
        
        # Step 4: Calculate confidence
        confidence = self._calculate_confidence(question, answer, results)
        
        # Step 5: Format response
        response = {
            'answer': answer,
            'evidence': [
                {
                    'text': chunk.text[:300],  # Truncate for display
                    'page': chunk.page,
                    'section': chunk.section,
                    'score': score
                }
                for chunk, score in evidence_chunks
            ],
            'confidence': confidence,
            'pages': list(set([chunk.page for chunk, _ in evidence_chunks])),
            'all_chunks': [
                {
                    'text': chunk.text,
                    'page': chunk.page,
                    'section': chunk.section
                }
                for chunk, score in evidence_chunks
            ]
        }
        
        return response
    
    def _extract_answer(self, question: str, chunks: List[Tuple[DocumentChunk, float]]) -> str:
        """Extract answer from retrieved chunks."""
        question_lower = question.lower()
        
        # Combine chunk texts
        combined_text = "\n\n".join([chunk[0].text for chunk in chunks])
        
        # Try to extract numeric answer for financial questions
        if any(kw in question_lower for kw in ['revenue', 'profit', 'ebitda', 'eps', 'dividend', 'cash flow']):
            # Look for currency values
            patterns = [
                r'₹\s*([\d,]+\.?\d*)\s*(crores?|cr)?',
                r'([\d,]+\.?\d*)\s*(crores?|cr)',
                r'\$\s*([\d,]+\.?\d*)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, combined_text, re.IGNORECASE)
                if matches:
                    value = matches[0][0].replace(',', '')
                    unit = matches[0][1] if len(matches[0]) > 1 else 'Crores'
                    return f"₹{value} {unit}"
        
        # For non-numeric questions, return relevant text
        # Find sentence containing question keywords
        sentences = re.split(r'(?<=[.!?])\s+', combined_text)
        
        question_words = set(question_lower.split())
        
        best_sentence = ""
        best_score = 0
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            score = sum(1 for word in question_words if word in sentence_lower and len(word) > 3)
            
            if score > best_score:
                best_score = score
                best_sentence = sentence
        
        if best_sentence:
            return best_sentence.strip()
        
        # Fallback: return first chunk
        return chunks[0][0].text[:500] if chunks else "Information not found."
    
    def _calculate_confidence(self, question: str, answer: str, results: List[Tuple[DocumentChunk, float]]) -> float:
        """Calculate confidence score for the answer."""
        if not results:
            return 0.0
        
        # Base confidence from similarity scores
        avg_similarity = sum(score for _, score in results) / len(results)
        
        # Boost if answer contains numbers (for financial queries)
        has_numbers = bool(re.search(r'[\d,]+', answer))
        
        # Boost if answer is not too short
        answer_length_score = min(len(answer) / 50, 1.0)
        
        # Combine scores
        confidence = (avg_similarity * 0.6) + (has_numbers * 0.2) + (answer_length_score * 0.2)
        
        return min(confidence, 1.0)
    
    def get_summary(self) -> Dict:
        """Get document summary."""
        return {
            'file_name': self.file_name,
            'total_pages': len(self.full_text),
            'total_chunks': len(self.chunks),
            'sections': self._get_section_summary(),
            'index_size': self.index.ntotal if self.index else 0
        }
    
    def _get_section_summary(self) -> Dict:
        """Get chunk count by section."""
        section_counts = {}
        for chunk in self.chunks:
            section = chunk.section
            section_counts[section] = section_counts.get(section, 0) + 1
        return section_counts


if __name__ == "__main__":
    # Test RAG analyzer
    pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"
    
    print("="*60)
    print("Testing RAG Document Analyzer")
    print("="*60)
    
    analyzer = RAGDocumentAnalyzer(pdf_path)
    analyzer.build_index(chunk_size=500, overlap=50)
    
    # Test query
    print("\nTest Query: What is the total revenue?")
    result = analyzer.query("What is the total revenue?")
    
    print(f"\nAnswer: {result['answer']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Pages: {result['pages']}")
    print(f"\nEvidence:")
    for i, ev in enumerate(result['evidence'][:2], 1):
        print(f"  {i}. Page {ev['page']} (Score: {ev['score']:.3f})")
        print(f"     {ev['text'][:150]}...")
