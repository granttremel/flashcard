#!/usr/bin/env python3

import re
import os
import json
import time
import heapq
import pickle
import requests
import networkx as nx
from typing import Dict, List, Set, Tuple, Optional, Union
from collections import defaultdict, Counter
from datetime import datetime
from urllib.parse import urlparse
import sqlite3
from contextlib import contextmanager

# Import existing components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flashcard.citations import Paper, Citation, CiteManager, CrossRefManager
from flashcard.archive.paper_database import PaperDatabase
from flashcard.wikipedia import WikiPage, WikiLink


class CrossNetworkConnection:
    """
    Represents connections between Wikipedia pages and academic papers.
    This is where the magic happens - bridging the two knowledge networks!
    """
    
    def __init__(self, wiki_page: WikiPage, paper: Paper, connection_type: str, confidence: float = 1.0):
        self.wiki_page = wiki_page
        self.paper = paper
        self.connection_type = connection_type  # "doi_reference", "title_match", "author_page", etc.
        self.confidence = confidence
        self.created_at = time.time()
    
    def __str__(self):
        return f"CrossConnection({self.wiki_page.title} <-> {self.paper.get_id()} [{self.connection_type}])"

class DOIExtractor:
    """
    Utility class to extract DOIs from Wikipedia external links.
    This is the key to bridging Wikipedia and citation networks!
    """
    
    def __init__(self):
        # Comprehensive DOI patterns
        self.doi_patterns = [
            re.compile(r'doi\.org/(10\.\d{4,}/[^\s<>\]"\']+)', re.IGNORECASE),
            re.compile(r'doi:\s*(10\.\d{4,}/[^\s<>\]"\']+)', re.IGNORECASE),
            re.compile(r'DOI:\s*(10\.\d{4,}/[^\s<>\]"\']+)', re.IGNORECASE),
            re.compile(r'dx\.doi\.org/(10\.\d{4,}/[^\s<>\]"\']+)', re.IGNORECASE),
        ]
    
    def extract_dois_from_links(self, external_links: List[Union[str, Dict]]) -> List[str]:
        """Extract DOIs from a list of external links."""
        dois = set()
        
        for link in external_links:
            # Handle different link formats
            if isinstance(link, dict):
                url = link.get('url', '')
                title = link.get('title', '')
                text_to_search = f"{url} {title}"
            else:
                text_to_search = str(link)
            
            # Apply all DOI patterns
            for pattern in self.doi_patterns:
                matches = pattern.findall(text_to_search)
                for match in matches:
                    # Clean up the DOI
                    clean_doi = self.clean_doi(match)
                    if clean_doi:
                        dois.add(clean_doi)
        
        return list(dois)
    
    def clean_doi(self, doi: str) -> str:
        """Clean and validate a DOI string."""
        # Remove common trailing characters
        doi = doi.strip('.,;)]}>\'"')
        
        # Remove HTML entities
        doi = doi.replace('&lt;', '<').replace('&gt;', '>')
        
        # Basic validation - must start with 10. and have a slash
        if doi.startswith('10.') and '/' in doi:
            return doi
        
        return None
    
    def extract_from_wiki_page_data(self, wiki_page_data: Dict) -> List[str]:
        """Extract DOIs from Wikipedia page data."""
        external_links = wiki_page_data.get('external_links', [])
        return self.extract_dois_from_links(external_links)

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
        
        self.G = nx.DiGraph()
        
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
    
    def add_node(self, paper, depth):
        paper_id = paper.get_id()
        self.G.add_node(paper_id, 
                title=str(paper),
                nciting=paper.nciting,
                ncited=paper.ncited,
                depth=depth)
    
    def add_edge(self, citation, citing_paper, cited_paper):
        
        self.G.add_edge(citing_paper.get_id(), cited_paper.get_id(), citation = citation.get_id())
     
    def get_network_analysis(self) -> Dict:
        """Get comprehensive network analysis including database stats."""
        db_stats = self.db.get_statistics()
        
        analysis = {
            'database_stats': db_stats,
            'crawler_stats': self.stats,
            'basic_stats': {
                'nodes': self.G.number_of_nodes(),
                'edges': self.G.number_of_edges(),
                'density': nx.density(self.G) if self.G.number_of_nodes() > 0 else 0,
                'is_connected': nx.is_weakly_connected(self.G) if self.G.number_of_nodes() > 1 else False
            },
            'performance_stats': {
                'papers_per_api_request': self.stats['papers_processed'] / max(self.stats['api_requests'], 1),
                'database_batches': self.stats['database_batches'],
                'avg_papers_per_batch': db_stats['total_papers'] / max(self.stats['database_batches'], 1)
            }
        }
        
        if self.G.number_of_nodes() > 1:
            analysis['centrality'] = {
                'degree': dict(sorted(nx.degree_centrality(self.G).items(), 
                                    key=lambda x: x[1], reverse=True)[:10]),
                'pagerank': dict(sorted(nx.pagerank(self.G).items(), 
                                      key=lambda x: x[1], reverse=True)[:10])
            }
        
        return analysis


class UnifiedDatabase(PaperDatabase):
    """
    Extended database that stores both academic papers and Wikipedia pages,
    plus the connections between them.
    """
    
    def init_database(self):
        """Initialize database with tables for papers, wiki pages, and cross-connections."""
        # First create the original paper tables
        super().init_database()
        
        # Add Wikipedia and cross-network tables
        with self.get_connection() as conn:
            conn.executescript("""
                -- Wikipedia pages table
                CREATE TABLE IF NOT EXISTS wiki_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    
                    -- Identifiers
                    title TEXT UNIQUE NOT NULL,
                    canonical_title TEXT,
                    page_id INTEGER,
                    
                    -- Content metadata
                    short_description TEXT,
                    main_definition TEXT,
                    categories TEXT,  -- JSON array
                    internal_links TEXT,  -- JSON array
                    external_links TEXT,  -- JSON array
                    images TEXT,  -- JSON array
                    
                    -- Network metrics
                    in_links INTEGER DEFAULT 0,
                    out_links INTEGER DEFAULT 0,
                    strength REAL DEFAULT 0.0,
                    
                    -- Classification
                    is_scientific BOOLEAN,
                    classification_confidence REAL DEFAULT 0.0,
                    
                    -- Extracted references
                    extracted_dois TEXT,  -- JSON array of DOIs found in external links
                    
                    -- Processing status
                    done BOOLEAN DEFAULT FALSE,
                    
                    -- Timestamps
                    created_at REAL DEFAULT (julianday('now')),
                    updated_at REAL DEFAULT (julianday('now'))
                );
                
                -- Wikipedia internal links table
                CREATE TABLE IF NOT EXISTS wiki_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_page_id INTEGER,
                    target_page_id INTEGER,
                    link_type TEXT DEFAULT 'internal',
                    created_at REAL DEFAULT (julianday('now')),
                    
                    FOREIGN KEY (source_page_id) REFERENCES wiki_pages (id),
                    FOREIGN KEY (target_page_id) REFERENCES wiki_pages (id)
                );
                
                -- Cross-network connections (Wikipedia <-> Papers)
                CREATE TABLE IF NOT EXISTS cross_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wiki_page_id INTEGER,
                    paper_id INTEGER,
                    connection_type TEXT,  -- 'doi_reference', 'title_match', etc.
                    confidence REAL DEFAULT 1.0,
                    created_at REAL DEFAULT (julianday('now')),
                    
                    FOREIGN KEY (wiki_page_id) REFERENCES wiki_pages (id),
                    FOREIGN KEY (paper_id) REFERENCES papers (id)
                );
                
                -- Indexes for Wikipedia tables
                CREATE UNIQUE INDEX IF NOT EXISTS idx_wiki_title ON wiki_pages (title);
                CREATE INDEX IF NOT EXISTS idx_wiki_page_id ON wiki_pages (page_id);
                CREATE INDEX IF NOT EXISTS idx_wiki_scientific ON wiki_pages (is_scientific);
                CREATE INDEX IF NOT EXISTS idx_wiki_strength ON wiki_pages (strength);
                
                CREATE INDEX IF NOT EXISTS idx_wiki_links_source ON wiki_links (source_page_id);
                CREATE INDEX IF NOT EXISTS idx_wiki_links_target ON wiki_links (target_page_id);
                
                CREATE INDEX IF NOT EXISTS idx_cross_wiki ON cross_connections (wiki_page_id);
                CREATE INDEX IF NOT EXISTS idx_cross_paper ON cross_connections (paper_id);
                CREATE INDEX IF NOT EXISTS idx_cross_type ON cross_connections (connection_type);
            """)
    
    def insert_wiki_page_batch(self, wiki_pages_data: List[Dict]) -> List[Optional[int]]:
        """Insert multiple Wikipedia pages in a batch."""
        if not wiki_pages_data:
            return []
        
        results = []
        self.begin_transaction()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for page_data in wiki_pages_data:
                    try:
                        # Convert lists to JSON
                        json_fields = ['categories', 'internal_links', 'external_links', 'images', 'extracted_dois']
                        for field in json_fields:
                            if field in page_data and isinstance(page_data[field], list):
                                page_data[field] = json.dumps(page_data[field])
                        
                        cursor.execute("""
                            INSERT INTO wiki_pages (
                                title, canonical_title, page_id, short_description, main_definition,
                                categories, internal_links, external_links, images,
                                in_links, out_links, strength, is_scientific, 
                                classification_confidence, extracted_dois, done
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            page_data.get('title'),
                            page_data.get('canonical_title'),
                            page_data.get('page_id'),
                            page_data.get('short_description', ''),
                            page_data.get('main_definition', ''),
                            page_data.get('categories', '[]'),
                            page_data.get('internal_links', '[]'),
                            page_data.get('external_links', '[]'),
                            page_data.get('images', '[]'),
                            page_data.get('in_links', 0),
                            page_data.get('out_links', 0),
                            page_data.get('strength', 0.0),
                            page_data.get('is_scientific'),
                            page_data.get('classification_confidence', 0.0),
                            page_data.get('extracted_dois', '[]'),
                            page_data.get('done', False)
                        ))
                        
                        results.append(cursor.lastrowid)
                        
                    except sqlite3.IntegrityError:
                        # Page already exists
                        cursor.execute("SELECT id FROM wiki_pages WHERE title = ?", (page_data.get('title'),))
                        result = cursor.fetchone()
                        results.append(result[0] if result else None)
                    except Exception as e:
                        print(f"Error inserting wiki page: {e}")
                        results.append(None)
                
                self.commit_transaction()
                return results
                
        except Exception as e:
            print(f"Wiki page batch insert failed: {e}")
            self.rollback_transaction()
            return [None] * len(wiki_pages_data)
    
    def insert_cross_connection_batch(self, connections_data: List[Tuple[int, int, str, float]]) -> List[Optional[int]]:
        """Insert cross-network connections in batch."""
        if not connections_data:
            return []
        
        results = []
        self.begin_transaction()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for wiki_page_id, paper_id, connection_type, confidence in connections_data:
                    try:
                        cursor.execute("""
                            INSERT INTO cross_connections (wiki_page_id, paper_id, connection_type, confidence)
                            VALUES (?, ?, ?, ?)
                        """, (wiki_page_id, paper_id, connection_type, confidence))
                        
                        results.append(cursor.lastrowid)
                        
                    except sqlite3.IntegrityError:
                        # Connection already exists
                        results.append(None)
                    except Exception as e:
                        print(f"Error inserting cross connection: {e}")
                        results.append(None)
                
                self.commit_transaction()
                return results
                
        except Exception as e:
            print(f"Cross connection batch insert failed: {e}")
            self.rollback_transaction()
            return [None] * len(connections_data)
    
    def get_cross_connections(self, wiki_page_id: int = None, paper_id: int = None) -> List[Dict]:
        """Get cross-network connections."""
        with self.get_connection() as conn:
            if wiki_page_id:
                cursor = conn.execute("""
                    SELECT cc.*, wp.title as wiki_title, p.doi as paper_doi
                    FROM cross_connections cc
                    JOIN wiki_pages wp ON cc.wiki_page_id = wp.id
                    JOIN papers p ON cc.paper_id = p.id
                    WHERE cc.wiki_page_id = ?
                """, (wiki_page_id,))
            elif paper_id:
                cursor = conn.execute("""
                    SELECT cc.*, wp.title as wiki_title, p.doi as paper_doi
                    FROM cross_connections cc
                    JOIN wiki_pages wp ON cc.wiki_page_id = wp.id
                    JOIN papers p ON cc.paper_id = p.id
                    WHERE cc.paper_id = ?
                """, (paper_id,))
            else:
                cursor = conn.execute("""
                    SELECT cc.*, wp.title as wiki_title, p.doi as paper_doi
                    FROM cross_connections cc
                    JOIN wiki_pages wp ON cc.wiki_page_id = wp.id
                    JOIN papers p ON cc.paper_id = p.id
                    LIMIT 100
                """)
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_unified_statistics(self) -> Dict:
        """Get statistics for the unified knowledge graph."""
        stats = self.get_statistics()  # Paper stats
        
        with self.get_connection() as conn:
            # Wikipedia stats
            cursor = conn.execute("SELECT COUNT(*) FROM wiki_pages")
            stats['total_wiki_pages'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM wiki_pages WHERE is_scientific = TRUE")
            stats['scientific_wiki_pages'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM wiki_links")
            stats['total_wiki_links'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM cross_connections")
            stats['cross_connections'] = cursor.fetchone()[0]
            
            # Connection type breakdown
            cursor = conn.execute("""
                SELECT connection_type, COUNT(*) 
                FROM cross_connections 
                GROUP BY connection_type
            """)
            stats['connection_types'] = dict(cursor.fetchall())
            
            # DOI extraction stats
            cursor = conn.execute("""
                SELECT COUNT(*) FROM wiki_pages 
                WHERE extracted_dois != '[]' AND extracted_dois IS NOT NULL
            """)
            stats['wiki_pages_with_dois'] = cursor.fetchone()[0]
            
        return stats


def test_unified_knowledge_system():
    """Test the unified knowledge graph system."""
    print("🔗 TESTING UNIFIED KNOWLEDGE GRAPH SYSTEM")
    print("="*50)
    
    # Create database
    db = UnifiedDatabase("./data/unified/test_knowledge_graph.db")
    
    # Test WikiPage creation
    wiki_page = WikiPage(
        title="CRISPR",
        short_description="Gene editing technology",
        categories=["Molecular biology", "Genetics", "Biotechnology"],
        external_links=[
            "https://doi.org/10.1038/nature12373",
            "https://www.ncbi.nlm.nih.gov/pmc/PMC1234567",
            "doi:10.1126/science.1234567"
        ],
        is_scientific=True,
        classification_confidence=0.95
    )
    
    # Extract DOIs
    extractor = DOIExtractor()
    dois = extractor.extract_from_wiki_page_data(wiki_page.to_dict())
    wiki_page.extracted_dois = dois
    
    print(f"✅ Created WikiPage: {wiki_page}")
    print(f"   Extracted DOIs: {dois}")
    
    # Insert into database
    wiki_data = [wiki_page.to_dict()]
    wiki_ids = db.insert_wiki_page_batch(wiki_data)
    print(f"✅ Inserted WikiPage with ID: {wiki_ids[0]}")
    
    # Create corresponding papers
    papers_data = []
    for doi in dois[:2]:  # Just test first 2
        paper_data = {
            'doi': doi,
            'title': f'Paper for {doi}',
            'nciting': 100,
            'ncited': 50
        }
        papers_data.append(paper_data)
    
    paper_ids = db.insert_paper_batch(papers_data)
    print(f"✅ Inserted {len(paper_ids)} papers")
    
    # Create cross-connections
    connections = []
    for paper_id in paper_ids:
        if paper_id:  # Skip failed inserts
            connections.append((wiki_ids[0], paper_id, "doi_reference", 1.0))
    
    connection_ids = db.insert_cross_connection_batch(connections)
    print(f"✅ Created {len(connection_ids)} cross-connections")
    
    # Get statistics
    stats = db.get_unified_statistics()
    print(f"\n📊 UNIFIED KNOWLEDGE GRAPH STATS:")
    print(f"   Wikipedia pages: {stats['total_wiki_pages']}")
    print(f"   Scientific pages: {stats['scientific_wiki_pages']}")
    print(f"   Academic papers: {stats['total_papers']}")
    print(f"   Cross-connections: {stats['cross_connections']}")
    print(f"   Wiki pages with DOIs: {stats['wiki_pages_with_dois']}")
    
    # Show connections
    cross_conns = db.get_cross_connections(wiki_page_id=wiki_ids[0])
    print(f"\n🔗 CROSS-CONNECTIONS:")
    for conn in cross_conns:
        print(f"   {conn['wiki_title']} <-> {conn['paper_doi']} [{conn['connection_type']}]")
    
    db.close_connection()
    print(f"\n✅ Unified knowledge graph test complete!")


if __name__ == "__main__":
    test_unified_knowledge_system()