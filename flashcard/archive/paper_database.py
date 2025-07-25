import sqlite3
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import time
from contextlib import contextmanager


class PaperDatabase:
    """
    High-performance SQLite database for storing paper metadata.
    Features connection pooling, transaction batching, and optimized queries.
    """
    
    def __init__(self, db_path: str = "./data/citations/papers.db"):
        self.db_path = db_path
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Connection settings for performance
        self._connection = None
        self._transaction_active = False
        self._batch_operations = []
        self._batch_size = 100
        
        # Initialize database
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections with performance settings."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                isolation_level=None  # Autocommit off for manual transaction control
            )
            
            # Performance optimizations
            cursor = self._connection.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
            cursor.execute("PRAGMA synchronous = NORMAL")  # Balance safety/speed
            cursor.execute("PRAGMA cache_size = 10000")   # 10MB cache
            cursor.execute("PRAGMA temp_store = MEMORY")   # Temp tables in RAM
            cursor.execute("PRAGMA mmap_size = 268435456") # 256MB memory map
            
        yield self._connection
    
    def close_connection(self):
        """Close the database connection."""
        if self._connection:
            if self._transaction_active:
                self._connection.commit()
                self._transaction_active = False
            self._connection.close()
            self._connection = None
    
    def __del__(self):
        """Cleanup on object deletion."""
        self.close_connection()
    
    def init_database(self):
        """Initialize database tables and indexes."""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    
                    -- Identifiers
                    doi TEXT,
                    pmid TEXT,
                    openalex TEXT,
                    omid TEXT,
                    isbn TEXT,
                    arxiv TEXT,
                    
                    -- Metadata from CrossRef
                    title TEXT,
                    authors TEXT,  -- JSON array of author names
                    issued_timestamp REAL,
                    issued_year INTEGER,
                    journal TEXT,
                    publisher TEXT,
                    
                    -- Citation metrics
                    nciting INTEGER DEFAULT 0,
                    ncited INTEGER DEFAULT 0,
                    strength REAL DEFAULT 0.0,
                    
                    -- Processing status
                    done BOOLEAN DEFAULT FALSE,
                    crossref_fetched BOOLEAN DEFAULT FALSE,
                    
                    -- Timestamps
                    created_at REAL DEFAULT (julianday('now')),
                    updated_at REAL DEFAULT (julianday('now'))
                );
                
                CREATE TABLE IF NOT EXISTS citations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    oci TEXT UNIQUE NOT NULL,
                    citing_paper_id INTEGER,
                    cited_paper_id INTEGER,
                    created_at REAL DEFAULT (julianday('now')),
                    
                    FOREIGN KEY (citing_paper_id) REFERENCES papers (id),
                    FOREIGN KEY (cited_paper_id) REFERENCES papers (id)
                );
                
                -- Unique indexes for identifiers (partial unique constraints)
                CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_doi_unique ON papers (doi) WHERE doi IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_pmid_unique ON papers (pmid) WHERE pmid IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_openalex_unique ON papers (openalex) WHERE openalex IS NOT NULL;
                
                -- Indexes for fast lookups
                CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers (doi);
                CREATE INDEX IF NOT EXISTS idx_papers_pmid ON papers (pmid);
                CREATE INDEX IF NOT EXISTS idx_papers_openalex ON papers (openalex);
                CREATE INDEX IF NOT EXISTS idx_papers_title ON papers (title);
                CREATE INDEX IF NOT EXISTS idx_papers_issued_year ON papers (issued_year);
                CREATE INDEX IF NOT EXISTS idx_papers_nciting ON papers (nciting);
                CREATE INDEX IF NOT EXISTS idx_papers_ncited ON papers (ncited);
                CREATE INDEX IF NOT EXISTS idx_papers_strength ON papers (strength);
                CREATE INDEX IF NOT EXISTS idx_papers_crossref_fetched ON papers (crossref_fetched);
                
                CREATE INDEX IF NOT EXISTS idx_citations_oci ON citations (oci);
                CREATE INDEX IF NOT EXISTS idx_citations_citing ON citations (citing_paper_id);
                CREATE INDEX IF NOT EXISTS idx_citations_cited ON citations (cited_paper_id);
            """)
    
    def begin_transaction(self):
        """Begin a database transaction for batch operations."""
        if not self._transaction_active:
            with self.get_connection() as conn:
                conn.execute("BEGIN TRANSACTION")
                self._transaction_active = True
    
    def commit_transaction(self):
        """Commit the current transaction."""
        if self._transaction_active:
            with self.get_connection() as conn:
                conn.commit()
                self._transaction_active = False
    
    def rollback_transaction(self):
        """Rollback the current transaction."""
        if self._transaction_active:
            with self.get_connection() as conn:
                conn.rollback()
                self._transaction_active = False
    
    def insert_paper_batch(self, papers_data: List[Dict]) -> List[Optional[int]]:
        """
        Insert multiple papers in a single transaction for better performance.
        
        Args:
            papers_data: List of paper dictionaries
            
        Returns:
            List of paper IDs (None for failed inserts)
        """
        if not papers_data:
            return []
        
        results = []
        self.begin_transaction()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for paper_data in papers_data:
                    try:
                        # Prepare data
                        identifiers = {
                            'doi': paper_data.get('doi'),
                            'pmid': paper_data.get('pmid'),
                            'openalex': paper_data.get('openalex'),
                            'omid': paper_data.get('omid'),
                            'isbn': paper_data.get('isbn'),
                            'arxiv': paper_data.get('arxiv')
                        }
                        
                        # Clean None values
                        identifiers = {k: v for k, v in identifiers.items() if v is not None}
                        
                        # Extract metadata
                        authors_json = json.dumps(paper_data.get('authors', [])) if paper_data.get('authors') else None
                        issued_timestamp = paper_data.get('issued_timestamp', 0)
                        issued_year = None
                        if issued_timestamp:
                            try:
                                issued_year = datetime.fromtimestamp(issued_timestamp).year
                            except (ValueError, OSError):
                                pass
                        
                        # Insert query
                        columns = list(identifiers.keys()) + [
                            'title', 'authors', 'issued_timestamp', 'issued_year', 
                            'journal', 'publisher', 'nciting', 'ncited', 'strength', 
                            'done', 'crossref_fetched'
                        ]
                        
                        values = list(identifiers.values()) + [
                            paper_data.get('title', ''),
                            authors_json,
                            issued_timestamp,
                            issued_year,
                            paper_data.get('journal', ''),
                            paper_data.get('publisher', ''),
                            paper_data.get('nciting', 0),
                            paper_data.get('ncited', 0),
                            paper_data.get('strength', 0.0),
                            paper_data.get('done', False),
                            paper_data.get('crossref_fetched', False)
                        ]
                        
                        placeholders = ', '.join(['?' for _ in values])
                        columns_str = ', '.join(columns)
                        
                        cursor.execute(
                            f"INSERT INTO papers ({columns_str}) VALUES ({placeholders})",
                            values
                        )
                        
                        results.append(cursor.lastrowid)
                        
                    except sqlite3.IntegrityError:
                        # Paper already exists, get existing ID
                        existing_id = self._get_paper_id_by_identifier_fast(cursor, paper_data)
                        results.append(existing_id)
                    except Exception as e:
                        print(f"Error inserting paper: {e}")
                        results.append(None)
                
                self.commit_transaction()
                return results
                
        except Exception as e:
            print(f"Batch insert failed: {e}")
            self.rollback_transaction()
            return [None] * len(papers_data)
    
    def insert_citations_batch(self, citations_data: List[Tuple[str, int, int]]) -> List[Optional[int]]:
        """
        Insert multiple citations in a single transaction.
        
        Args:
            citations_data: List of (oci, citing_paper_id, cited_paper_id) tuples
            
        Returns:
            List of citation IDs (None for failed inserts)
        """
        if not citations_data:
            return []
        
        results = []
        self.begin_transaction()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for oci, citing_id, cited_id in citations_data:
                    try:
                        cursor.execute("""
                            INSERT INTO citations (oci, citing_paper_id, cited_paper_id)
                            VALUES (?, ?, ?)
                        """, (oci, citing_id, cited_id))
                        
                        results.append(cursor.lastrowid)
                        
                    except sqlite3.IntegrityError:
                        # Citation already exists
                        results.append(None)
                    except Exception as e:
                        print(f"Error inserting citation: {e}")
                        results.append(None)
                
                self.commit_transaction()
                return results
                
        except Exception as e:
            print(f"Citation batch insert failed: {e}")
            self.rollback_transaction()
            return [None] * len(citations_data)
    
    def _get_paper_id_by_identifier_fast(self, cursor, paper_data: Dict) -> Optional[int]:
        """Fast paper ID lookup using existing cursor."""
        # Try each identifier type
        for id_type in ['doi', 'pmid', 'openalex', 'omid', 'isbn', 'arxiv']:
            if paper_data.get(id_type):
                cursor.execute(
                    f"SELECT id FROM papers WHERE {id_type} = ?",
                    (paper_data[id_type],)
                )
                result = cursor.fetchone()
                if result:
                    return result[0]
        return None
    
    # Keep the single-operation methods for compatibility
    def insert_paper(self, paper_data: Dict) -> Optional[int]:
        """Insert a single paper (uses batch method internally)."""
        results = self.insert_paper_batch([paper_data])
        return results[0] if results else None
    
    def insert_citation(self, oci: str, citing_paper_id: int, cited_paper_id: int) -> Optional[int]:
        """Insert a single citation (uses batch method internally)."""
        results = self.insert_citations_batch([(oci, citing_paper_id, cited_paper_id)])
        return results[0] if results else None
    
    def get_paper_id_by_identifier(self, paper_data: Dict) -> Optional[int]:
        """Get paper ID by any available identifier."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            return self._get_paper_id_by_identifier_fast(cursor, paper_data)
    
    def update_paper_metadata_batch(self, updates: List[Tuple[int, Dict]]) -> int:
        """
        Update metadata for multiple papers in a single transaction.
        
        Args:
            updates: List of (paper_id, metadata_dict) tuples
            
        Returns:
            Number of successfully updated papers
        """
        if not updates:
            return 0
        
        updated_count = 0
        self.begin_transaction()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for paper_id, metadata in updates:
                    try:
                        # Prepare update data
                        authors_json = None
                        if metadata.get('authors'):
                            authors_json = json.dumps(metadata['authors'])
                        
                        issued_timestamp = metadata.get('issued_timestamp', 0)
                        issued_year = None
                        if issued_timestamp:
                            try:
                                issued_year = datetime.fromtimestamp(issued_timestamp).year
                            except (ValueError, OSError):
                                pass
                        
                        cursor.execute("""
                            UPDATE papers SET
                                title = COALESCE(?, title),
                                authors = COALESCE(?, authors),
                                issued_timestamp = COALESCE(?, issued_timestamp),
                                issued_year = COALESCE(?, issued_year),
                                journal = COALESCE(?, journal),
                                publisher = COALESCE(?, publisher),
                                crossref_fetched = TRUE,
                                updated_at = julianday('now')
                            WHERE id = ?
                        """, (
                            metadata.get('title'),
                            authors_json,
                            issued_timestamp if issued_timestamp else None,
                            issued_year,
                            metadata.get('journal'),
                            metadata.get('publisher'),
                            paper_id
                        ))
                        
                        if cursor.rowcount > 0:
                            updated_count += 1
                            
                    except Exception as e:
                        print(f"Error updating paper {paper_id}: {e}")
                
                self.commit_transaction()
                return updated_count
                
        except Exception as e:
            print(f"Batch metadata update failed: {e}")
            self.rollback_transaction()
            return 0
    
    # Keep all the read methods from the original class
    def get_papers_without_metadata(self, limit: int = 100) -> List[Dict]:
        """Get papers that need CrossRef metadata fetching."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, doi, pmid, openalex, omid, isbn, arxiv, title
                FROM papers 
                WHERE crossref_fetched = FALSE AND doi IS NOT NULL
                ORDER BY nciting DESC, ncited DESC
                LIMIT ?
            """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def search_papers(self, query: str = None, **filters) -> List[Dict]:
        """Search papers by various criteria."""
        with self.get_connection() as conn:
            where_clauses = []
            params = []
            
            if query:
                where_clauses.append("(title LIKE ? OR authors LIKE ?)")
                query_param = f"%{query}%"
                params.extend([query_param, query_param])
            
            if filters.get('issued_year'):
                where_clauses.append("issued_year = ?")
                params.append(filters['issued_year'])
            
            if filters.get('min_nciting'):
                where_clauses.append("nciting >= ?")
                params.append(filters['min_nciting'])
            
            if filters.get('min_ncited'):
                where_clauses.append("ncited >= ?")
                params.append(filters['min_ncited'])
            
            if filters.get('journal'):
                where_clauses.append("journal LIKE ?")
                params.append(f"%{filters['journal']}%")
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            cursor = conn.execute(f"""
                SELECT id, doi, title, authors, issued_year, journal, 
                       nciting, ncited, strength, crossref_fetched
                FROM papers 
                WHERE {where_sql}
                ORDER BY strength DESC, nciting DESC
                LIMIT ?
            """, params + [filters.get('limit', 100)])
            
            columns = [desc[0] for desc in cursor.description]
            papers = []
            for row in cursor.fetchall():
                paper = dict(zip(columns, row))
                # Parse authors JSON
                if paper['authors']:
                    try:
                        paper['authors'] = json.loads(paper['authors'])
                    except json.JSONDecodeError:
                        paper['authors'] = []
                papers.append(paper)
            return papers
    
    def get_top_papers(self, metric: str = 'nciting', limit: int = 100) -> List[Dict]:
        """Get top papers by a specific metric."""
        valid_metrics = ['nciting', 'ncited', 'strength', 'issued_year']
        if metric not in valid_metrics:
            metric = 'nciting'
        
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT id, doi, title, authors, issued_year, journal, 
                       nciting, ncited, strength, crossref_fetched
                FROM papers 
                WHERE {metric} IS NOT NULL AND {metric} > 0
                ORDER BY {metric} DESC
                LIMIT ?
            """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            papers = []
            for row in cursor.fetchall():
                paper = dict(zip(columns, row))
                # Parse authors JSON
                if paper['authors']:
                    try:
                        paper['authors'] = json.loads(paper['authors'])
                    except json.JSONDecodeError:
                        paper['authors'] = []
                papers.append(paper)
            return papers
    
    def get_statistics(self) -> Dict:
        """Get database statistics."""
        with self.get_connection() as conn:
            stats = {}
            
            # Paper counts
            cursor = conn.execute("SELECT COUNT(*) FROM papers")
            stats['total_papers'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM papers WHERE crossref_fetched = TRUE")
            stats['papers_with_metadata'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM papers WHERE done = TRUE")
            stats['processed_papers'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM citations")
            stats['total_citations'] = cursor.fetchone()[0]
            
            # Citation metrics
            cursor = conn.execute("SELECT AVG(nciting), MAX(nciting) FROM papers WHERE nciting > 0")
            result = cursor.fetchone()
            stats['avg_nciting'] = result[0] or 0
            stats['max_nciting'] = result[1] or 0
            
            cursor = conn.execute("SELECT AVG(ncited), MAX(ncited) FROM papers WHERE ncited > 0")
            result = cursor.fetchone()
            stats['avg_ncited'] = result[0] or 0
            stats['max_ncited'] = result[1] or 0
            
            # Year distribution
            cursor = conn.execute("""
                SELECT issued_year, COUNT(*) 
                FROM papers 
                WHERE issued_year IS NOT NULL 
                GROUP BY issued_year 
                ORDER BY issued_year DESC
                LIMIT 10
            """)
            stats['recent_years'] = dict(cursor.fetchall())
            
            # Top journals
            cursor = conn.execute("""
                SELECT journal, COUNT(*) 
                FROM papers 
                WHERE journal IS NOT NULL AND journal != ''
                GROUP BY journal 
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """)
            stats['top_journals'] = dict(cursor.fetchall())
            
            return stats
    
    def export_to_json(self, output_file: str, limit: int = None) -> bool:
        """Export papers to JSON for backup/analysis."""
        try:
            with self.get_connection() as conn:
                if limit:
                    cursor = conn.execute("""
                        SELECT * FROM papers 
                        ORDER BY strength DESC, nciting DESC 
                        LIMIT ?
                    """, (limit,))
                else:
                    cursor = conn.execute("SELECT * FROM papers")
                
                columns = [desc[0] for desc in cursor.description]
                papers = []
                
                for row in cursor.fetchall():
                    paper = dict(zip(columns, row))
                    # Parse authors JSON
                    if paper['authors']:
                        try:
                            paper['authors'] = json.loads(paper['authors'])
                        except json.JSONDecodeError:
                            paper['authors'] = []
                    papers.append(paper)
                
                with open(output_file, 'w') as f:
                    json.dump(papers, f, indent=2, default=str)
                
                print(f"Exported {len(papers)} papers to {output_file}")
                return True
                
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            return False
    
    def mark_paper_done(self, paper_id: int) -> bool:
        """Mark a paper as processed."""
        with self.get_connection() as conn:
            try:
                conn.execute("UPDATE papers SET done = TRUE WHERE id = ?", (paper_id,))
                return True
            except Exception as e:
                print(f"Error marking paper done: {e}")
                return False
    
    def update_paper_citations(self, paper_id: int, nciting: int = None, ncited: int = None, strength: float = None) -> bool:
        """Update paper citation counts and strength."""
        with self.get_connection() as conn:
            try:
                conn.execute("""
                    UPDATE papers SET
                        nciting = COALESCE(?, nciting),
                        ncited = COALESCE(?, ncited),
                        strength = COALESCE(?, strength)
                    WHERE id = ?
                """, (nciting, ncited, strength, paper_id))
                
                return True
                
            except Exception as e:
                print(f"Error updating paper citations: {e}")
                return False


def test_optimized_database():
    """Test the optimized database performance."""
    print("🚀 Testing OptimizedPaperDatabase performance...")
    
    db = PaperDatabase("./data/citations/test_optimized.db")
    
    # Test batch insertion
    test_papers = []
    for i in range(100):
        test_papers.append({
            'doi': f'10.1001/test.{i:04d}',
            'title': f'Test Paper {i}',
            'authors': [f'Author {i}', f'Co-Author {i}'],
            'issued_timestamp': time.time(),
            'nciting': i * 2,
            'ncited': i,
            'strength': i * 3
        })
    
    start_time = time.time()
    paper_ids = db.insert_paper_batch(test_papers)
    batch_time = time.time() - start_time
    
    print(f"✅ Batch insert of 100 papers: {batch_time:.3f}s")
    print(f"   Average per paper: {(batch_time/100)*1000:.1f}ms")
    
    # Test citation batch insertion
    citation_data = []
    for i in range(50):
        citation_data.append((f'test-{i}-{i+1}', paper_ids[i], paper_ids[i+1]))
    
    start_time = time.time()
    citation_ids = db.insert_citations_batch(citation_data)
    citation_time = time.time() - start_time
    
    print(f"✅ Batch insert of 50 citations: {citation_time:.3f}s")
    
    # Test metadata batch update
    metadata_updates = []
    for i in range(20):
        metadata_updates.append((paper_ids[i], {
            'title': f'Updated Test Paper {i}',
            'journal': f'Test Journal {i}',
            'publisher': 'Test Publisher'
        }))
    
    start_time = time.time()
    updated_count = db.update_paper_metadata_batch(metadata_updates)
    metadata_time = time.time() - start_time
    
    print(f"✅ Batch metadata update of 20 papers: {metadata_time:.3f}s")
    
    # Show stats
    stats = db.get_statistics()
    print(f"📊 Final database: {stats['total_papers']} papers, {stats['total_citations']} citations")
    
    db.close_connection()
    return batch_time, citation_time, metadata_time


if __name__ == "__main__":
    test_optimized_database()