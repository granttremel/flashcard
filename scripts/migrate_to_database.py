#!/usr/bin/env python3

import sys
import os
import pickle
import json
import time
from typing import Dict, List, Set, Optional

# Add project root to path
sys.path.append('.')

from flashcard.paper_database import PaperDatabase
from flashcard.citations_refactored import Paper, Citation


class CitationDataMigrator:
    """
    Migrate citation data from old in-memory format to new database format.
    Handles pickle state files from the original citation crawler.
    """
    
    def __init__(self, db_path: str = "./data/citations/migrated_papers.db"):
        self.db = PaperDatabase(db_path)
        self.stats = {
            'papers_migrated': 0,
            'citations_migrated': 0,
            'errors': 0,
            'start_time': None
        }
    
    def migrate_from_pickle_state(self, state_file: str) -> bool:
        """
        Migrate data from pickle state file to database.
        
        Args:
            state_file: Path to pickle state file from old crawler
            
        Returns:
            True if migration successful, False otherwise
        """
        if not os.path.exists(state_file):
            print(f"❌ State file not found: {state_file}")
            return False
        
        print(f"📂 Loading state from: {state_file}")
        self.stats['start_time'] = time.time()
        
        try:
            with open(state_file, 'rb') as f:
                state = pickle.load(f)
            
            print(f"✅ State file loaded successfully")
            
            # Extract data from state
            processed_papers = set(state.get('processed_papers', []))
            papers_by_id = state.get('papers_by_id', {})
            graph_data = state.get('graph_data', {'nodes': [], 'edges': []})
            paper_references = state.get('paper_references', {})
            
            print(f"📊 Found in state file:")
            print(f"   Processed papers: {len(processed_papers)}")
            print(f"   Papers by ID: {len(papers_by_id)}")
            print(f"   Graph nodes: {len(graph_data.get('nodes', []))}")
            print(f"   Graph edges: {len(graph_data.get('edges', []))}")
            
            # Migrate papers
            self._migrate_papers(papers_by_id, processed_papers, paper_references)
            
            # Migrate citations from graph
            self._migrate_citations_from_graph(graph_data)
            
            # Print results
            elapsed = time.time() - self.stats['start_time']
            print(f"\n✅ MIGRATION COMPLETE")
            print(f"   Runtime: {elapsed:.1f} seconds")
            print(f"   Papers migrated: {self.stats['papers_migrated']}")
            print(f"   Citations migrated: {self.stats['citations_migrated']}")
            print(f"   Errors: {self.stats['errors']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            return False
    
    def _migrate_papers(self, papers_by_id: Dict, processed_papers: Set, 
                       paper_references: Dict):
        """Migrate papers to database."""
        print(f"\n📄 Migrating papers...")
        
        for paper_id, paper_data in papers_by_id.items():
            try:
                # Handle different paper data formats
                if isinstance(paper_data, str):
                    # Simple string representation
                    paper_dict = {
                        'title': paper_data,
                        'done': paper_id in processed_papers,
                        'nciting': 0,
                        'ncited': 0,
                        'strength': paper_references.get(paper_id, 0)
                    }
                    
                    # Try to extract identifier from paper_id
                    if ':' in paper_id:
                        id_type, id_value = paper_id.split(':', 1)
                        if id_type in ['doi', 'pmid', 'openalex', 'omid', 'isbn', 'arxiv']:
                            paper_dict[id_type] = id_value
                    else:
                        # Assume it's a DOI if it looks like one
                        if '10.' in paper_id and '/' in paper_id:
                            paper_dict['doi'] = paper_id
                        else:
                            paper_dict['title'] = paper_id
                
                elif hasattr(paper_data, 'to_dict'):
                    # Paper object with to_dict method
                    paper_dict = paper_data.to_dict()
                    paper_dict['done'] = paper_id in processed_papers
                    
                elif isinstance(paper_data, dict):
                    # Already a dictionary
                    paper_dict = paper_data.copy()
                    paper_dict['done'] = paper_id in processed_papers
                    
                else:
                    print(f"⚠️  Unknown paper data format for {paper_id}: {type(paper_data)}")
                    continue
                
                # Insert into database
                db_id = self.db.insert_paper(paper_dict)
                if db_id:
                    self.stats['papers_migrated'] += 1
                    if self.stats['papers_migrated'] % 100 == 0:
                        print(f"   Migrated {self.stats['papers_migrated']} papers...")
                
            except Exception as e:
                print(f"⚠️  Error migrating paper {paper_id}: {e}")
                self.stats['errors'] += 1
        
        print(f"✅ Paper migration complete: {self.stats['papers_migrated']} papers")
    
    def _migrate_citations_from_graph(self, graph_data: Dict):
        """Migrate citations from graph data."""
        print(f"\n🔗 Migrating citations...")
        
        edges = graph_data.get('edges', [])
        
        for edge in edges:
            try:
                if len(edge) >= 3:
                    citing_id, cited_id, edge_data = edge[0], edge[1], edge[2]
                    
                    # Get citation identifier
                    oci = None
                    if isinstance(edge_data, dict):
                        oci = edge_data.get('citation')
                    
                    if not oci:
                        # Generate a dummy OCI if none exists
                        oci = f"migration-{citing_id}-{cited_id}".replace(':', '-')[:50]
                    
                    # Get database IDs for papers
                    citing_db_id = self._find_paper_db_id(citing_id)
                    cited_db_id = self._find_paper_db_id(cited_id)
                    
                    if citing_db_id and cited_db_id:
                        citation_id = self.db.insert_citation(oci, citing_db_id, cited_db_id)
                        if citation_id:
                            self.stats['citations_migrated'] += 1
                            
                            if self.stats['citations_migrated'] % 100 == 0:
                                print(f"   Migrated {self.stats['citations_migrated']} citations...")
                
            except Exception as e:
                print(f"⚠️  Error migrating citation: {e}")
                self.stats['errors'] += 1
        
        print(f"✅ Citation migration complete: {self.stats['citations_migrated']} citations")
    
    def _find_paper_db_id(self, paper_id: str) -> Optional[int]:
        """Find database ID for a paper by its identifier."""
        # Try different identifier formats
        search_data = {}
        
        if ':' in paper_id:
            id_type, id_value = paper_id.split(':', 1)
            if id_type in ['doi', 'pmid', 'openalex', 'omid', 'isbn', 'arxiv']:
                search_data[id_type] = id_value
        else:
            # Try as DOI
            if '10.' in paper_id and '/' in paper_id:
                search_data['doi'] = paper_id
        
        if search_data:
            return self.db.get_paper_id_by_identifier(search_data)
        
        return None
    
    def migrate_from_json_export(self, json_file: str) -> bool:
        """
        Migrate data from JSON export file.
        
        Args:
            json_file: Path to JSON file with paper data
            
        Returns:
            True if migration successful, False otherwise
        """
        if not os.path.exists(json_file):
            print(f"❌ JSON file not found: {json_file}")
            return False
        
        print(f"📄 Loading data from: {json_file}")
        self.stats['start_time'] = time.time()
        
        try:
            with open(json_file, 'r') as f:
                papers_data = json.load(f)
            
            print(f"✅ JSON file loaded: {len(papers_data)} papers")
            
            # Migrate papers
            for paper_data in papers_data:
                try:
                    db_id = self.db.insert_paper(paper_data)
                    if db_id:
                        self.stats['papers_migrated'] += 1
                        
                        if self.stats['papers_migrated'] % 100 == 0:
                            print(f"   Migrated {self.stats['papers_migrated']} papers...")
                
                except Exception as e:
                    print(f"⚠️  Error migrating paper: {e}")
                    self.stats['errors'] += 1
            
            elapsed = time.time() - self.stats['start_time']
            print(f"\n✅ JSON MIGRATION COMPLETE")
            print(f"   Runtime: {elapsed:.1f} seconds")
            print(f"   Papers migrated: {self.stats['papers_migrated']}")
            print(f"   Errors: {self.stats['errors']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during JSON migration: {e}")
            return False


def find_migration_candidates():
    """Find files that can be migrated to database."""
    print("🔍 SEARCHING FOR MIGRATION CANDIDATES")
    print("="*40)
    
    candidates = []
    
    # Look for pickle state files
    pickle_patterns = [
        "./data/citation_crawler_state.pkl",
        "./data/citation_crawler_state_1.pkl",
        "./data/citations/crawler_state.pkl"
    ]
    
    for pattern in pickle_patterns:
        if os.path.exists(pattern):
            size = os.path.getsize(pattern) / 1024  # KB
            candidates.append(('pickle', pattern, f"{size:.1f} KB"))
            print(f"📦 Found pickle state: {pattern} ({size:.1f} KB)")
    
    # Look for JSON exports
    json_patterns = [
        "./data/citations/papers_export.json",
        "./data/citations/network_analysis.json"
    ]
    
    for pattern in json_patterns:
        if os.path.exists(pattern):
            size = os.path.getsize(pattern) / 1024  # KB
            candidates.append(('json', pattern, f"{size:.1f} KB"))
            print(f"📄 Found JSON export: {pattern} ({size:.1f} KB)")
    
    if not candidates:
        print("❌ No migration candidates found")
        print("   Run the original citation crawler first to generate data")
    else:
        print(f"\n✅ Found {len(candidates)} migration candidates")
    
    return candidates


def migrate_all_found_data():
    """Automatically migrate all found data files."""
    print("🔄 AUTOMATIC MIGRATION OF ALL FOUND DATA")
    print("="*45)
    
    candidates = find_migration_candidates()
    
    if not candidates:
        return
    
    # Create migrator
    migrator = CitationDataMigrator("./data/citations/auto_migrated_papers.db")
    
    total_migrated = 0
    
    for file_type, file_path, size_info in candidates:
        print(f"\n📂 Processing {file_type.upper()}: {file_path}")
        
        if file_type == 'pickle':
            success = migrator.migrate_from_pickle_state(file_path)
        elif file_type == 'json':
            success = migrator.migrate_from_json_export(file_path)
        else:
            print(f"⚠️  Unknown file type: {file_type}")
            continue
        
        if success:
            total_migrated += migrator.stats['papers_migrated']
            print(f"✅ Successfully migrated {migrator.stats['papers_migrated']} papers")
        else:
            print(f"❌ Migration failed for {file_path}")
    
    # Show final database stats
    if total_migrated > 0:
        final_stats = migrator.db.get_statistics()
        print(f"\n🎉 MIGRATION SUMMARY")
        print(f"   Total papers in database: {final_stats['total_papers']}")
        print(f"   Total citations: {final_stats['total_citations']}")
        print(f"   Database location: {migrator.db.db_path}")
        
        db_size = os.path.getsize(migrator.db.db_path) / (1024 * 1024)  # MB
        print(f"   Database size: {db_size:.1f} MB")


def interactive_migration():
    """Interactive migration tool."""
    print("🔧 INTERACTIVE MIGRATION TOOL")
    print("="*30)
    
    candidates = find_migration_candidates()
    
    if not candidates:
        print("No files to migrate. Exiting.")
        return
    
    print(f"\nSelect files to migrate:")
    for i, (file_type, file_path, size_info) in enumerate(candidates, 1):
        print(f"   {i}. [{file_type.upper()}] {file_path} ({size_info})")
    
    try:
        choice = input(f"\nEnter choice (1-{len(candidates)}) or 'all': ").strip().lower()
        
        if choice == 'all':
            migrate_all_found_data()
            return
        
        choice_idx = int(choice) - 1
        if 0 <= choice_idx < len(candidates):
            file_type, file_path, _ = candidates[choice_idx]
            
            # Get output database path
            default_db = f"./data/citations/migrated_from_{file_type}.db"
            db_path = input(f"Database path (default: {default_db}): ").strip()
            if not db_path:
                db_path = default_db
            
            # Perform migration
            migrator = CitationDataMigrator(db_path)
            
            print(f"\n🔄 Starting migration...")
            if file_type == 'pickle':
                success = migrator.migrate_from_pickle_state(file_path)
            else:
                success = migrator.migrate_from_json_export(file_path)
            
            if success:
                print(f"\n🎉 Migration successful!")
                print(f"   Database: {db_path}")
                
                # Show stats
                stats = migrator.db.get_statistics()
                print(f"   Papers: {stats['total_papers']}")
                print(f"   Citations: {stats['total_citations']}")
            else:
                print(f"\n❌ Migration failed")
        
        else:
            print("Invalid choice")
    
    except (ValueError, KeyboardInterrupt):
        print("\nMigration cancelled")


def main():
    """Main migration function."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command in ['--find', '-f']:
            find_migration_candidates()
        elif command in ['--auto', '-a']:
            migrate_all_found_data()
        elif command in ['--interactive', '-i']:
            interactive_migration()
        elif command in ['--help', '-h']:
            print("🔄 Citation Data Migration Tool")
            print("\nMigrate citation data from old in-memory format to new database format")
            print("\nUsage:")
            print("  python migrate_to_database.py --find        # Find files that can be migrated")
            print("  python migrate_to_database.py --auto        # Automatically migrate all found files")
            print("  python migrate_to_database.py --interactive # Interactive migration tool")
            print("  python migrate_to_database.py <pickle_file> # Migrate specific pickle file")
        else:
            # Treat as file path
            pickle_file = sys.argv[1]
            migrator = CitationDataMigrator()
            migrator.migrate_from_pickle_state(pickle_file)
    else:
        interactive_migration()


if __name__ == "__main__":
    main()