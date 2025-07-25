#!/usr/bin/env python3

import sys
import os
import json
import time
from datetime import datetime

# Add project root to path
sys.path.append('.')

from flashcard.citations_with_database import DatabaseIntegratedCitationCrawler
from flashcard.citations_refactored import CiteManager, CrossRefManager, Paper
from flashcard.paper_database import PaperDatabase


def demo_database_citation_crawler():
    """Demonstrate the database-integrated citation crawler."""
    
    print("🗄️ DATABASE-INTEGRATED CITATION CRAWLER DEMO")
    print("="*60)
    print("This demo showcases:")
    print("✅ SQLite database for efficient paper storage")
    print("✅ CrossRef metadata fetching")
    print("✅ Handling 37k+ papers efficiently")
    print("✅ Resumable crawling sessions")
    print("✅ Comprehensive network analysis")
    print()
    
    # Create managers
    cite_manager = CiteManager()
    crossref_manager = CrossRefManager()
    
    # Create database crawler
    db_path = "./data/citations/papers_demo.db"
    crawler = DatabaseIntegratedCitationCrawler(
        cite_manager, 
        crossref_manager,
        db_path=db_path,
        state_file="./data/citation_crawler_demo_state_1.pkl"
    )
    
    # Set crawler parameters
    crawler.max_depth = 2
    crawler.max_papers = 20  # Start small for demo
    crawler.crossref_batch_size = 5  # Fetch metadata in small batches
    
    # Create seed papers with diverse research areas
    seed_papers = [
        # Medical research
        Paper(doi="10.1001/jama.2020.1585"),  # COVID-19 related
        
        # Biotechnology
        Paper(doi="10.1038/nature12373"),     # CRISPR gene editing
        
        # Add more if you want larger network
        Paper(doi="10.1126/science.1259855"), # Another high-impact paper
    ]
    
    print(f"🌱 Adding {len(seed_papers)} seed papers:")
    for paper in seed_papers:
        print(f"   📄 {paper}")
    
    crawler.add_seed_papers(seed_papers)
    
    # Show initial database stats
    initial_stats = crawler.db.get_statistics()
    print(f"\n📊 Initial Database State:")
    print(f"   Papers: {initial_stats['total_papers']}")
    print(f"   With metadata: {initial_stats['papers_with_metadata']}")
    print(f"   Citations: {initial_stats['total_citations']}")
    
    # Start crawling
    print(f"\n🚀 Starting intelligent database-backed citation crawl...")
    print(f"   Max papers: {crawler.max_papers}")
    print(f"   Max depth: {crawler.max_depth}")
    print(f"   Database: {db_path}")
    print(f"   The crawler will:")
    print(f"   • Store all papers in SQLite for efficiency")
    print(f"   • Fetch CrossRef metadata in batches")
    print(f"   • Prioritize papers with high citation counts")
    print(f"   • Save progress for resuming later")
    print(f"   • Handle thousands of papers efficiently")
    print(f"\n⏱️  Press Ctrl+C to stop at any time\n")
    
    start_time = time.time()
    
    try:
        # Crawl with time limit for demo
        crawler.crawl_network(max_papers=crawler.max_papers, max_time_hours=0.1)  # 6 minutes max
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Demo stopped by user")
    
    elapsed = time.time() - start_time
    
    # Show final results
    print(f"\n🏁 DEMO COMPLETE - Runtime: {elapsed/60:.1f} minutes")
    
    # Database statistics
    final_stats = crawler.db.get_statistics()
    print(f"\n📊 FINAL DATABASE STATISTICS:")
    print(f"   📄 Total papers: {final_stats['total_papers']}")
    print(f"   ✅ Papers with metadata: {final_stats['papers_with_metadata']}")
    print(f"   🔗 Total citations: {final_stats['total_citations']}")
    print(f"   📈 Average citations per paper: {final_stats.get('avg_nciting', 0):.1f}")
    print(f"   🎯 Most cited paper: {final_stats.get('max_nciting', 0)} citations")
    
    # Show recent years distribution
    if final_stats.get('recent_years'):
        print(f"\n📅 Publication Years (Top 5):")
        for year, count in list(final_stats['recent_years'].items())[:5]:
            print(f"      {year}: {count} papers")
    
    # Show top journals
    if final_stats.get('top_journals'):
        print(f"\n📚 Top Journals (Top 5):")
        for journal, count in list(final_stats['top_journals'].items())[:5]:
            journal_name = journal[:50] + "..." if len(journal) > 50 else journal
            print(f"      {count:2d} papers: {journal_name}")
    
    # Network analysis
    # analysis = crawler.get_network_analysis()
    # network_stats = analysis['basic_stats']
    
    # print(f"\n🕸️  CITATION NETWORK ANALYSIS:")
    # print(f"   Nodes: {network_stats['nodes']}")
    # print(f"   Edges: {network_stats['edges']}")
    # print(f"   Density: {network_stats['density']:.4f}")
    # print(f"   Connected: {network_stats['is_connected']}")
    
    # Show top papers from database
    print(f"\n🏆 TOP PAPERS BY CITATION COUNT:")
    top_papers = crawler.db.get_top_papers(metric='nciting', limit=10)
    for i, paper in enumerate(top_papers[:10], 1):
        title = paper.get('title', '')[:60] + '...' if len(paper.get('title', '')) > 60 else paper.get('title', '')
        title = title or paper.get('doi', 'Unknown DOI')
        authors_list = paper.get('authors', [])
        first_author = authors_list[0] if authors_list else "Unknown"
        year = paper.get('issued_year') or 'Unknown'
        
        print(f"   {i:2d}. [{paper['nciting']:3d} cites] {title}")
        print(f"       {first_author} et al. ({year})")
    
    # # Show top papers by PageRank if available
    # if 'centrality' in analysis and analysis['centrality'].get('pagerank'):
    #     print(f"\n⭐ MOST INFLUENTIAL PAPERS (PageRank):")
    #     for i, (paper_id, score) in enumerate(list(analysis['centrality']['pagerank'].items())[:5], 1):
    #         print(f"   {i}. {paper_id}: {score:.4f}")
    
    # Export data
    print(f"\n💾 EXPORTING DATA...")
    export_dir = f"./data/citations/demo_export_{int(time.time())}"
    exports = crawler.export_network_data(export_dir)
    
    print(f"   📁 Export directory: {export_dir}")
    print(f"   📊 Database JSON: {exports['database_json']}")
    print(f"   📈 Analysis JSON: {exports['analysis']}")
    if exports.get('network'):
        print(f"   🕸️  Network GraphML: {exports['network']}")
    
    # Database file info
    db_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
    print(f"\n💽 Database file: {db_path} ({db_size:.1f} MB)")
    
    # Resumption instructions
    print(f"\n🔄 TO RESUME CRAWLING LATER:")
    print(f"   The crawler automatically saves its state.")
    print(f"   Simply run this demo again to continue where you left off!")
    print(f"   To crawl more papers:")
    print(f"   ```python")
    print(f"   crawler = DatabaseIntegratedCitationCrawler(cite_manager, crossref_manager)")
    print(f"   crawler.max_papers = 1000  # Scale up!")
    print(f"   crawler.crawl_network()")
    print(f"   ```")
    
    print(f"\n✨ Demo complete! Check out the database and exported files.")


def explore_existing_database():
    """Explore an existing citation database."""
    db_path = "./data/citations/papers_demo.db"
    
    if not os.path.exists(db_path):
        print("❌ No existing database found")
        print("   Run the demo first to create a database")
        return
    
    print("🔍 EXPLORING EXISTING CITATION DATABASE")
    print("="*45)
    
    # Load database
    db = PaperDatabase(db_path)
    stats = db.get_statistics()
    
    print(f"📊 Database Overview:")
    print(f"   Location: {db_path}")
    print(f"   Size: {os.path.getsize(db_path) / (1024*1024):.1f} MB")
    print(f"   Papers: {stats['total_papers']}")
    print(f"   With metadata: {stats['papers_with_metadata']}")
    print(f"   Citations: {stats['total_citations']}")
    
    # Search examples
    print(f"\n🔍 SEARCH EXAMPLES:")
    
    # Search by year
    recent_papers = db.search_papers(issued_year=2020, limit=5)
    print(f"\n   📅 Papers from 2020 ({len(recent_papers)} found):")
    for paper in recent_papers[:3]:
        title = paper.get('title', 'No title')[:50] + '...' if len(paper.get('title', '')) > 50 else paper.get('title', 'No title')
        print(f"      • {title}")
    
    # Search by keyword
    covid_papers = db.search_papers(query="COVID", limit=5)
    print(f"\n   🦠 COVID-related papers ({len(covid_papers)} found):")
    for paper in covid_papers[:3]:
        title = paper.get('title', 'No title')[:50] + '...' if len(paper.get('title', '')) > 50 else paper.get('title', 'No title')
        print(f"      • {title}")
    
    # High-impact papers
    high_impact = db.search_papers(min_nciting=100, limit=5)
    print(f"\n   📈 High-impact papers (100+ citations, {len(high_impact)} found):")
    for paper in high_impact[:3]:
        title = paper.get('title', 'No title')[:50] + '...' if len(paper.get('title', '')) > 50 else paper.get('title', 'No title')
        print(f"      • [{paper['nciting']} cites] {title}")
    
    # Top journals
    if stats.get('top_journals'):
        print(f"\n📚 Top Journals:")
        for journal, count in list(stats['top_journals'].items())[:5]:
            journal_name = journal[:40] + "..." if len(journal) > 40 else journal
            print(f"      {count:3d} papers: {journal_name}")
    
    # Export sample
    print(f"\n💾 Exporting sample to JSON...")
    sample_file = "./data/citations/database_sample.json"
    db.export_to_json(sample_file, limit=100)
    
    print(f"✅ Exploration complete! Sample exported to: {sample_file}")


def compare_storage_approaches():
    """Compare in-memory vs database storage approaches."""
    print("⚖️  STORAGE APPROACH COMPARISON")
    print("="*40)
    
    print("📝 IN-MEMORY STORAGE (Original):")
    print("   ✅ Fast access to individual papers")
    print("   ✅ Simple priority queue operations")
    print("   ❌ Limited by RAM (can't handle 37k+ papers)")
    print("   ❌ All progress lost on crash")
    print("   ❌ No metadata persistence")
    print("   ❌ Difficult to analyze large datasets")
    
    print("\n🗄️  DATABASE STORAGE (New):")
    print("   ✅ Handles unlimited number of papers")
    print("   ✅ Persistent storage survives crashes")
    print("   ✅ Efficient querying and search")
    print("   ✅ Automatic metadata management")
    print("   ✅ Perfect for large-scale analysis")
    print("   ⚠️  Slightly slower individual access")
    print("   ⚠️  More complex setup")
    
    print("\n📊 PERFORMANCE COMPARISON:")
    print("   Dataset Size    | In-Memory | Database")
    print("   --------------- | --------- | --------")
    print("   100 papers      | Fast      | Fast")
    print("   1,000 papers    | Fast      | Fast")
    print("   10,000 papers   | Slow      | Fast")
    print("   37,000+ papers  | Crashes   | Fast")
    
    print("\n🎯 RECOMMENDATION:")
    print("   Use DATABASE STORAGE for:")
    print("   • Large-scale citation networks (1000+ papers)")
    print("   • Long-running crawling sessions")
    print("   • Research analysis and publications")
    print("   • Production environments")
    
    print("\n   Use IN-MEMORY storage for:")
    print("   • Small experiments (< 500 papers)")
    print("   • Quick prototyping")
    print("   • Single-session analysis")


def migration_demo():
    """Demonstrate migrating from in-memory to database storage."""
    print("🔄 MIGRATION FROM IN-MEMORY TO DATABASE")
    print("="*45)
    
    # Check if old state file exists
    old_state_file = "./data/citation_crawler_state.pkl"
    
    if not os.path.exists(old_state_file):
        print("❌ No existing in-memory state found")
        print("   This demo shows how to migrate existing data")
        return
    
    print("📂 Found existing crawler state file")
    print("   This contains papers and citations from previous crawling")
    print("   Let's migrate this data to our new database!")
    
    # Load old state (this would need the old crawler format)
    print("\n⚠️  Migration script would need to:")
    print("   1. Load papers from pickle state file")
    print("   2. Create new database")
    print("   3. Insert all papers with proper identifiers")
    print("   4. Recreate citation relationships")
    print("   5. Fetch missing CrossRef metadata")
    
    print("\n💡 For now, starting fresh with database is recommended!")


def main():
    """Main demo function with different modes."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command in ['--explore', '-e']:
            explore_existing_database()
        elif command in ['--compare', '-c']:
            compare_storage_approaches()
        elif command in ['--migrate', '-m']:
            migration_demo()
        elif command in ['--help', '-h']:
            print("🗄️ Database Citation Crawler Demo")
            print("\nUsage:")
            print("  python demo_database_citation_crawler.py          # Run main demo")
            print("  python demo_database_citation_crawler.py --explore # Explore existing database")
            print("  python demo_database_citation_crawler.py --compare # Compare storage approaches")
            print("  python demo_database_citation_crawler.py --migrate # Migration demo")
        else:
            print(f"Unknown command: {command}")
            print("Use --help for available commands")
    else:
        demo_database_citation_crawler()


if __name__ == "__main__":
    main()