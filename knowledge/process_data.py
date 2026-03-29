"""
NUST Admission Bot — Data Processing Engine v2.0
=================================================
Takes raw PDFs and text files → outputs clean, enriched,
deduplicated chunks in unified format ready for embedding.

Usage:
    python process_everything.py

Input:  data/raw/  (PDFs + .txt files)
Output: data/processed/chunks.json
        data/processed/qa_pairs.json
        data/processed/stats.json
"""

import os
import re
import sys
import json
import hashlib
from collections import Counter

try:
    import pdfplumber
except ImportError:
    print("❌ Install pdfplumber: pip install pdfplumber")
    exit(1)

# Allow importing config from any working directory
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_MODULE_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import RAW_DIR, PROCESSED_DIR, QA_PAIRS_FILE

# ============================================================
# CONFIGURATION — Tune these for your setup
# ============================================================
CONFIG = {
    "raw_dir": RAW_DIR,
    "output_dir": PROCESSED_DIR,
    "max_chunk_words": 120,       # ~120 words per chunk (sweet spot)
    "min_chunk_words": 20,        # skip fragments smaller than this
    "overlap_words": 25,          # overlap between consecutive chunks
    "min_chunk_chars": 50,        # absolute minimum chunk size
}

# Category detection keywords — add more as needed
CATEGORY_KEYWORDS = {
    "fees": ["fee", "tuition", "charges", "payment", "cost", "dues",
             "semester fee", "hostel fee", "security deposit"],
    "merit": ["merit", "aggregate", "formula", "weightage", "net score",
              "marks", "percentage", "cutoff", "cut-off"],
    "eligibility": ["eligible", "eligibility", "requirement", "qualification",
                     "criteria", "fsc", "a-level", "matric", "o-level",
                     "intermediate"],
    "admission_process": ["apply", "application", "registration", "how to apply",
                          "admission process", "step", "procedure", "deadline"],
    "net_test": ["net", "entry test", "test date", "test pattern", "syllabus",
                 "test center", "test score", "nust entry test"],
    "programs": ["program", "degree", "bscs", "bsee", "bsme", "bsce",
                 "bachelor", "engineering", "school", "seecs", "smme",
                 "sns", "nbs", "sada", "scme", "nice", "igis"],
    "hostel": ["hostel", "accommodation", "residence", "room", "mess",
               "boarding", "lodging"],
    "scholarships": ["scholarship", "financial aid", "waiver", "need-based",
                     "merit-based", "stipend"],
    "campus": ["campus", "facility", "library", "lab", "sports", "transport",
               "clinic", "cafeteria"],
    "contact": ["contact", "phone", "email", "address", "helpline", "office"],
    "dates": ["deadline", "last date", "schedule", "calendar", "important date",
              "session", "semester start"],
}

# Query normalization map — synonyms users might type
SYNONYM_MAP = {
    "cost": "fee",
    "price": "fee",
    "money": "fee",
    "marks": "merit",
    "score": "merit",
    "cutoff": "merit",
    "stay": "hostel",
    "dorm": "hostel",
    "courses": "programs",
    "subjects": "programs",
    "apply": "admission_process",
    "register": "admission_process",
    "exam": "net_test",
}


# ============================================================
# PDF PARSER
# ============================================================
class PDFParser:
    """Extract text and tables from PDF files."""

    def extract(self, pdf_path):
        """Returns list of page dicts with text and/or tables."""
        pages = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_num = i + 1

                    # Extract text
                    text = page.extract_text()
                    if text and len(text.strip()) > 30:
                        pages.append({
                            "page": page_num,
                            "type": "text",
                            "content": text.strip()
                        })

                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for t_idx, table in enumerate(tables):
                            if table and len(table) > 1:  # need header + data
                                pages.append({
                                    "page": page_num,
                                    "type": "table",
                                    "content": table,
                                    "table_index": t_idx
                                })
        except Exception as e:
            print(f"  ❌ PDF Error: {e}")

        return pages


# ============================================================
# TEXT CLEANER
# ============================================================
class TextCleaner:
    """Clean raw text from web scraping or PDF extraction."""

    @staticmethod
    def clean(text):
        """Remove noise while preserving meaningful content."""
        if not text:
            return ""

        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Remove excessive newlines (3+ → 2)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remove non-printable chars but keep English, Urdu, numbers, punctuation
        text = re.sub(r'[^\x20-\x7E\u0600-\u06FF\n.,!?()%/:;@#&*\-–—\'"]+', ' ', text)

        # Collapse multiple spaces
        text = re.sub(r' {2,}', ' ', text)

        # Clean up space before punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)

        # Strip each line
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        return text.strip()

    @staticmethod
    def table_to_natural_language(table_data, page_context=""):
        """
        Convert raw table into natural language sentences.
        
        Instead of: "Program: BSCS, Fee: 150000"
        Produces:   "The fee for BSCS is 150,000 PKR."
        """
        if not table_data or len(table_data) < 2:
            return ""

        sentences = []
        if page_context:
            sentences.append(page_context)

        # Clean headers
        headers = []
        for h in table_data[0]:
            if h:
                cleaned = str(h).strip().replace('\n', ' ')
                headers.append(cleaned)
            else:
                headers.append("")

        # Process each row
        for row in table_data[1:]:
            if not row:
                continue

            parts = []
            for i, cell in enumerate(row):
                if cell and i < len(headers):
                    cell_clean = str(cell).strip().replace('\n', ' ')
                    header_clean = headers[i]

                    if header_clean:
                        parts.append(f"{header_clean}: {cell_clean}")
                    else:
                        parts.append(cell_clean)

            if parts:
                # Create a readable sentence from the row
                sentence = ". ".join(parts) + "."
                sentences.append(sentence)

        return "\n".join(sentences)


# ============================================================
# CATEGORY DETECTOR
# ============================================================
class CategoryDetector:
    """Automatically detect what topic a chunk belongs to."""

    @staticmethod
    def detect(text, source=""):
        """Returns the best matching category for the text."""
        combined = (text + " " + source).lower()
        scores = {}

        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores, key=scores.get)
        return "general"

    @staticmethod
    def detect_all(text, source=""):
        """Returns all matching categories sorted by relevance."""
        combined = (text + " " + source).lower()
        scores = {}

        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > 0:
                scores[category] = score

        return sorted(scores.keys(), key=lambda k: scores[k], reverse=True)


# ============================================================
# KEYWORD EXTRACTOR
# ============================================================
class KeywordExtractor:
    """Extract important keywords for BM25 search boosting."""

    # Common stopwords to skip
    STOPWORDS = {
        "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need",
        "a", "an", "and", "but", "or", "nor", "not", "so", "yet",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "under", "again", "further", "then", "once",
        "here", "there", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "more", "most", "other", "some", "such",
        "no", "only", "own", "same", "than", "too", "very", "just",
        "because", "about", "also", "this", "that", "these", "those",
        "it", "its", "they", "them", "their", "we", "our", "you", "your",
        "he", "she", "him", "her", "his", "which", "who", "whom",
        "what", "if", "while", "per", "upon", "any", "must",
    }

    @classmethod
    def extract(cls, text, max_keywords=12):
        """Extract meaningful keywords from text."""
        # Tokenize
        words = re.findall(r'[a-zA-Z]{3,}', text.lower())

        # Filter stopwords and very short words
        meaningful = [w for w in words if w not in cls.STOPWORDS and len(w) > 2]

        # Count frequency
        counts = Counter(meaningful)

        # Also grab NUST-specific terms (always include if present)
        nust_terms = [
            "nust", "net", "seecs", "smme", "sns", "nbs", "sada",
            "scme", "nice", "igis", "bscs", "bsee", "bsme", "bsce",
            "aggregate", "merit", "fee", "hostel", "scholarship",
            "prospectus", "admission", "undergraduate", "postgraduate",
        ]
        priority = [t for t in nust_terms if t in text.lower()]

        # Combine: priority terms first, then by frequency
        result = list(dict.fromkeys(priority + [w for w, _ in counts.most_common(max_keywords)]))
        return result[:max_keywords]


# ============================================================
# SECTION DETECTOR
# ============================================================
class SectionDetector:
    """Detect section boundaries in text (headings, topic shifts)."""

    @staticmethod
    def split_into_sections(text):
        """
        Split text into sections based on:
        1. Markdown-style headers (# Header)
        2. ALL CAPS HEADINGS
        3. Double newlines (paragraph boundaries)
        """
        # Pattern: markdown headers OR ALL CAPS lines (5+ chars)
        pattern = r'(?=\n#{1,3}\s+)|(?=\n[A-Z][A-Z\s]{4,}\n)'

        sections = re.split(pattern, text)

        # Clean and filter
        result = []
        for section in sections:
            section = section.strip()
            if section and len(section) > CONFIG["min_chunk_chars"]:
                # Try to extract title from the section
                lines = section.split('\n')
                title = ""

                # Check if first line looks like a heading
                first_line = lines[0].strip()
                if first_line.startswith('#'):
                    title = first_line.lstrip('#').strip()
                    section = '\n'.join(lines[1:]).strip()
                elif first_line.isupper() and len(first_line) > 3:
                    title = first_line.title()
                    section = '\n'.join(lines[1:]).strip()

                if section:  # might be empty after removing title
                    result.append({
                        "title": title,
                        "content": section
                    })

        return result if result else [{"title": "", "content": text}]


# ============================================================
# SEMANTIC CHUNKER (THE CORE ENGINE)
# ============================================================
class SemanticChunker:
    """
    Paragraph-aware chunking that respects meaning boundaries.
    
    Instead of blindly splitting every N words, this:
    1. Splits by paragraphs first
    2. Groups small paragraphs together
    3. Splits large paragraphs by sentences
    4. Never cuts mid-sentence
    """

    def __init__(self, max_words=120, min_words=20, overlap_words=25):
        self.max_words = max_words
        self.min_words = min_words
        self.overlap_words = overlap_words

    def chunk(self, text, title=""):
        """Split text into semantic chunks."""
        if not text or len(text.strip()) < CONFIG["min_chunk_chars"]:
            return []

        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        # If no paragraph breaks, split by single newlines
        if len(paragraphs) == 1:
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        chunks = []
        current_chunk_parts = []
        current_word_count = 0

        for para in paragraphs:
            para_words = len(para.split())

            # If this paragraph alone exceeds max, split by sentences
            if para_words > self.max_words:
                # First, save what we have
                if current_chunk_parts:
                    chunk_text = ' '.join(current_chunk_parts)
                    chunks.append(chunk_text)
                    current_chunk_parts = []
                    current_word_count = 0

                # Split the large paragraph by sentences
                sentence_chunks = self._split_by_sentences(para)
                chunks.extend(sentence_chunks)
                continue

            # If adding this paragraph exceeds max, save current and start new
            if current_word_count + para_words > self.max_words and current_chunk_parts:
                chunk_text = ' '.join(current_chunk_parts)
                chunks.append(chunk_text)

                # Keep overlap: last part for context continuity
                if self.overlap_words > 0 and current_chunk_parts:
                    overlap_text = ' '.join(current_chunk_parts[-1:])
                    overlap_wc = len(overlap_text.split())
                    if overlap_wc <= self.overlap_words:
                        current_chunk_parts = [overlap_text]
                        current_word_count = overlap_wc
                    else:
                        current_chunk_parts = []
                        current_word_count = 0
                else:
                    current_chunk_parts = []
                    current_word_count = 0

            current_chunk_parts.append(para)
            current_word_count += para_words

        # Don't forget the last chunk
        if current_chunk_parts and current_word_count >= self.min_words:
            chunk_text = ' '.join(current_chunk_parts)
            chunks.append(chunk_text)

        # Prefix title to each chunk for context
        if title:
            chunks = [f"{title}\n\n{chunk}" for chunk in chunks]

        return chunks

    def _split_by_sentences(self, text):
        """Split a large paragraph into chunks by sentence boundaries."""
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current = []
        current_wc = 0

        for sentence in sentences:
            s_wc = len(sentence.split())

            if current_wc + s_wc > self.max_words and current:
                chunks.append(' '.join(current))
                current = []
                current_wc = 0

            current.append(sentence)
            current_wc += s_wc

        if current and current_wc >= self.min_words:
            chunks.append(' '.join(current))

        return chunks


# ============================================================
# DEDUPLICATOR
# ============================================================
class Deduplicator:
    """Remove duplicate or near-duplicate chunks."""

    def __init__(self):
        self.seen_hashes = set()

    def is_duplicate(self, text):
        """Check if we've seen this content before."""
        # Normalize for comparison
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        content_hash = hashlib.md5(normalized.encode()).hexdigest()

        if content_hash in self.seen_hashes:
            return True

        self.seen_hashes.add(content_hash)
        return False

    def is_near_duplicate(self, text, threshold=0.85):
        """
        Check for near-duplicates using word overlap.
        This catches chunks that are slightly different but essentially the same.
        """
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        words = set(normalized.split())

        for existing_hash in self.seen_hashes:
            # We only store hashes, so this is just exact duplicate check
            # For true near-duplicate detection, we'd need to store texts
            pass

        # For this implementation, exact hash is sufficient
        return self.is_duplicate(text)


# ============================================================
# MAIN PROCESSING ENGINE
# ============================================================
class ProcessingEngine:
    """
    The main orchestrator that ties everything together.
    
    Pipeline:
    Raw files → Parse → Clean → Detect sections → Chunk → 
    Enrich → Deduplicate → Classify → Save
    """

    def __init__(self):
        self.pdf_parser = PDFParser()
        self.cleaner = TextCleaner()
        self.chunker = SemanticChunker(
            max_words=CONFIG["max_chunk_words"],
            min_words=CONFIG["min_chunk_words"],
            overlap_words=CONFIG["overlap_words"],
        )
        self.deduplicator = Deduplicator()
        self.section_detector = SectionDetector()

        self.all_chunks = []    # unified output
        self.qa_pairs = []      # Q&A fast-path pairs
        self.stats = Counter()  # processing statistics

    def process_directory(self, raw_dir):
        """Process all files in the raw data directory."""
        if not os.path.exists(raw_dir):
            print(f"❌ Directory not found: {raw_dir}")
            return

        files = sorted(os.listdir(raw_dir))
        print(f"📂 Found {len(files)} files in {raw_dir}\n")

        for filename in files:
            filepath = os.path.join(raw_dir, filename)

            if filename.endswith('.txt'):
                self._process_text_file(filepath, filename)
            elif filename.endswith('.pdf'):
                self._process_pdf_file(filepath, filename)
            elif filename.endswith('.md'):
                self._process_text_file(filepath, filename)
            else:
                print(f"  ⏭️  Skipping: {filename}")
                self.stats["skipped"] += 1

        # Post-processing
        self._generate_qa_pairs()
        self._print_stats()

    def _process_text_file(self, filepath, filename):
        """Process a scraped web page text file."""
        print(f"📄 Processing: {filename}")

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse metadata from header lines
        lines = content.split('\n')
        url = ""
        title = filename.replace('.txt', '').replace('_', ' ').title()

        # Check for metadata headers
        content_start = 0
        for i, line in enumerate(lines):
            if line.startswith("SOURCE_URL:"):
                url = line.replace("SOURCE_URL:", "").strip()
                content_start = i + 1
            elif line.startswith("SOURCE_TITLE:"):
                title = line.replace("SOURCE_TITLE:", "").strip()
                content_start = i + 1
            elif line.startswith("URL:"):
                url = line.replace("URL:", "").strip()
                content_start = i + 1
            elif line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
                content_start = i + 1
            else:
                break

        text_body = '\n'.join(lines[content_start:])

        # Clean
        cleaned = self.cleaner.clean(text_body)
        if not cleaned or len(cleaned) < 50:
            print(f"  ⚠️  Too short after cleaning, skipping")
            self.stats["skipped"] += 1
            return

        # Detect sections
        sections = self.section_detector.split_into_sections(cleaned)

        # Chunk each section
        for section in sections:
            section_title = section["title"] or title
            chunks = self.chunker.chunk(section["content"], title=section_title)

            for chunk_text in chunks:
                self._add_chunk(
                    text=chunk_text,
                    source=title,
                    url=url,
                    source_type="web",
                )

        self.stats["text_files"] += 1

    def _process_pdf_file(self, filepath, filename):
        """Process a PDF file (prospectus, fee structure, etc.)."""
        print(f"📕 Processing PDF: {filename}")

        pages = self.pdf_parser.extract(filepath)
        pdf_name = filename.replace('.pdf', '').replace('_', ' ').title()

        for page_data in pages:
            page_num = page_data["page"]

            if page_data["type"] == "text":
                cleaned = self.cleaner.clean(page_data["content"])
                if not cleaned or len(cleaned) < 50:
                    continue

                sections = self.section_detector.split_into_sections(cleaned)

                for section in sections:
                    section_title = section["title"] or f"{pdf_name} - Page {page_num}"
                    chunks = self.chunker.chunk(section["content"], title=section_title)

                    for chunk_text in chunks:
                        self._add_chunk(
                            text=chunk_text,
                            source=f"{pdf_name} (Page {page_num})",
                            url="",
                            source_type="pdf",
                            page=page_num,
                        )

            elif page_data["type"] == "table":
                context = f"Data from {pdf_name}, Page {page_num}"
                natural_text = self.cleaner.table_to_natural_language(
                    page_data["content"],
                    page_context=context
                )

                if natural_text and len(natural_text) > 30:
                    # Tables might be long — chunk them too
                    chunks = self.chunker.chunk(natural_text, title=context)

                    for chunk_text in chunks:
                        self._add_chunk(
                            text=chunk_text,
                            source=f"{pdf_name} (Table, Page {page_num})",
                            url="",
                            source_type="pdf_table",
                            page=page_num,
                        )

        self.stats["pdf_files"] += 1

    def _add_chunk(self, text, source, url="", source_type="web", page=None):
        """
        Create an enriched chunk and add to the collection.
        This is the UNIFIED FORMAT — every chunk looks the same
        regardless of where it came from.
        """
        # Skip if too short
        if len(text.split()) < CONFIG["min_chunk_words"]:
            self.stats["skipped_short"] += 1
            return

        # Deduplicate
        if self.deduplicator.is_duplicate(text):
            self.stats["duplicates_removed"] += 1
            return

        # Detect category
        category = CategoryDetector.detect(text, source)

        # Extract keywords
        keywords = KeywordExtractor.extract(text)

        # Build the unified chunk object
        chunk = {
            "id": f"chunk_{len(self.all_chunks):04d}",
            "type": "chunk",
            "category": category,
            "content": text,
            "keywords": keywords,
            "source": source,
            "source_type": source_type,
            "url": url,
            "word_count": len(text.split()),
        }

        if page:
            chunk["page"] = page

        self.all_chunks.append(chunk)
        self.stats["chunks_created"] += 1

    def _generate_qa_pairs(self):
        """
        Load manually curated Q&A pairs.
        Auto-generation from regex was producing garbage — removed.
        """
        print("\nLoading Q&A pairs...")

        qa_path = os.path.join(CONFIG["output_dir"], "qa_pairs.json")

        if os.path.exists(qa_path):
            # If manual QA file already exists, don't overwrite
            with open(qa_path, "r", encoding="utf-8") as f:
                self.qa_pairs = json.load(f)
            print(f"  Loaded {len(self.qa_pairs)} existing Q&A pairs (manual)")
        else:
            # Create minimal starter QA
            self.qa_pairs = []
            print("  No qa_pairs.json found. Create it manually.")
            print("  See the template in the documentation.")

    def _print_stats(self):
        """Print processing statistics."""
        print("\n" + "=" * 60)
        print("📊 PROCESSING STATISTICS")
        print("=" * 60)
        print(f"  Text files processed:  {self.stats['text_files']}")
        print(f"  PDF files processed:   {self.stats['pdf_files']}")
        print(f"  Files skipped:         {self.stats['skipped']}")
        print(f"  Chunks created:        {self.stats['chunks_created']}")
        print(f"  Duplicates removed:    {self.stats['duplicates_removed']}")
        print(f"  Short chunks skipped:  {self.stats['skipped_short']}")
        print(f"  Q&A pairs:             {len(self.qa_pairs)}")
        print()

        # Category distribution
        categories = Counter(c["category"] for c in self.all_chunks)
        print("  📂 Category Distribution:")
        for cat, count in categories.most_common():
            bar = "█" * min(count, 40)
            print(f"     {cat:25s} {count:4d}  {bar}")

        # Word count stats
        word_counts = [c["word_count"] for c in self.all_chunks]
        if word_counts:
            print(f"\n  📏 Chunk Size (words):")
            print(f"     Min: {min(word_counts)}")
            print(f"     Max: {max(word_counts)}")
            print(f"     Avg: {sum(word_counts) // len(word_counts)}")
        print("=" * 60)

    def save(self):
        """Save all processed data."""
        output_dir = CONFIG["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        # Save chunks
        chunks_path = os.path.join(output_dir, "chunks.json")
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(self.all_chunks, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Chunks saved:   {chunks_path} ({len(self.all_chunks)} items)")

        # Save Q&A pairs
        qa_path = os.path.join(output_dir, "qa_pairs.json")
        with open(qa_path, 'w', encoding='utf-8') as f:
            json.dump(self.qa_pairs, f, indent=2, ensure_ascii=False)
        print(f"✅ Q&A saved:      {qa_path} ({len(self.qa_pairs)} items)")

        # Save stats
        stats_data = {
            "total_chunks": len(self.all_chunks),
            "total_qa_pairs": len(self.qa_pairs),
            "categories": dict(Counter(c["category"] for c in self.all_chunks)),
            "processing_stats": dict(self.stats),
            "config_used": CONFIG,
        }
        stats_path = os.path.join(output_dir, "stats.json")
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, indent=2)
        print(f"✅ Stats saved:    {stats_path}")

        # Save synonym map for retrieval layer
        syn_path = os.path.join(output_dir, "synonyms.json")
        with open(syn_path, 'w', encoding='utf-8') as f:
            json.dump(SYNONYM_MAP, f, indent=2)
        print(f"✅ Synonyms saved: {syn_path}")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 NUST Admission Bot — Data Processing Engine v2.0")
    print("=" * 60)
    print()

    engine = ProcessingEngine()
    engine.process_directory(CONFIG["raw_dir"])
    engine.save()

    print("\n🎉 Done! Your data is ready for embedding.")
    print("   Next step: Build the retrieval index (Phase 2)")