#!/usr/bin/env python3

from flashcard.citations_refactored import IntelligentCitationCrawler, CiteManager, Paper
import json
import os

def demo_citation_crawler():
    """Demonstrate the intelligent citation crawler."""
    
    print("📚 INTELLIGENT CITATION CRAWLER DEMO")
    print("="*60)
    
    # Create citation manager and crawler
    cite_manager = CiteManager()
    crawler = IntelligentCitationCrawler(
        cite_manager,
        data_dir="./data/citations",
        state_file="./data/citation_crawler_state_1.pkl"
        # state_file = ""
    )
    
    # Set crawler parameters for demo
    crawler.max_depth = 2      # How deep to go
    crawler.max_papers = 20    # Limit for demo
    
    # Create seed papers (examples of academic papers)
    seed_papers = [
        # COVID-19 research paper
        Paper(doi="10.1001/jama.2020.1585"),
        
        # Nature paper on CRISPR
        Paper(doi="10.1038/nature12373"),
        
        # If you have PMID or other identifiers:
        # Paper(pmid="32044947"),
        # Paper(openalex="W3001234567"),
    ]
    
    print(f"Adding {len(seed_papers)} seed papers...")
    for paper in seed_papers:
        print(f"  📄 {paper}")
    
    crawler.add_seed_papers(seed_papers)
    
    # Start crawling
    print("\nStarting intelligent citation crawl...")
    print("The crawler will:")
    print("- Prioritize papers with high citation counts")
    print("- Build a comprehensive citation network")
    print("- Track paper references and relationships")
    print("- Save progress for resuming later")
    print("- Respect OpenCitations API rate limits")
    print("\nPress Ctrl+C to stop at any time\n")
    
    # Crawl with time limit for demo
    crawler.crawl_network(max_papers=1, max_time_hours=0.05)  # 3 minutes max
    
    print(crawler.stats)
    
    # Show what we discovered
    print("\n🔬 ANALYZING CITATION NETWORK...")
    analysis = crawler.get_network_analysis()
    
    if 'error' not in analysis:
        basic_stats = analysis['basic_stats']
        print(f"✅ Network built with:")
        print(f"   📄 {basic_stats['nodes']} papers")
        print(f"   🔗 {basic_stats['edges']} citations")
        print(f"   🌐 Density: {basic_stats['density']:.4f}")
        print(f"   🔄 Connected: {basic_stats['is_connected']}")
        
        print(f"\n🏆 Top papers by reference count:")
        for paper_id, count in list(analysis['top_papers'].items())[:10]:
            paper = crawler.papers_by_id.get(paper_id, paper_id)
            print(f"      • {paper}: {count} references")
        
        # Show centrality analysis if available
        if 'centrality' in analysis:
            print(f"\n⭐ Most central papers (PageRank):")
            for paper_id, score in list(analysis['centrality']['pagerank'].items())[:5]:
                paper = crawler.papers_by_id.get(paper_id, paper_id)
                print(f"      • {paper}: {score:.4f}")
    
    # Create visualization
    print(f"\n📊 CREATING NETWORK VISUALIZATION...")
    try:
        crawler.visualize_network(save_path='./data/citations/network_viz.png')
    except Exception as e:
        print(f"Visualization failed: {e}")
    
    # Save analysis
    with open('./data/citations/network_analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2, default=str)
    
    print(f"\n💾 Results saved:")
    print(f"   📊 Network analysis: ./data/citations/network_analysis.json")
    print(f"   🎨 Visualization: ./data/citations/network_viz.png")
    print(f"   💿 Crawler state: ./data/citation_crawler_state.pkl")
    
    print(f"\n🔄 To resume crawling later:")
    print(f"   crawler = IntelligentCitationCrawler(cite_manager)")
    print(f"   crawler.crawl_network(max_papers=100)")


def explore_existing_network():
    """Explore a previously built citation network."""
    state_file = "./data/citation_crawler_state.pkl"
    
    if not os.path.exists(state_file):
        print("❌ No existing citation network found")
        print("   Run the demo first to build a network")
        return
    
    print("🔍 EXPLORING EXISTING CITATION NETWORK")
    print("="*45)
    
    # Load existing crawler
    cite_manager = CiteManager()
    crawler = IntelligentCitationCrawler(cite_manager)
    
    if crawler.G.number_of_nodes() == 0:
        print("❌ No network data found")
        return
    
    # Show network statistics
    analysis = crawler.get_network_analysis()
    basic_stats = analysis['basic_stats']
    
    print(f"📊 Network Statistics:")
    print(f"   Papers: {basic_stats['nodes']}")
    print(f"   Citations: {basic_stats['edges']}")
    print(f"   Density: {basic_stats['density']:.4f}")
    print(f"   Connected: {basic_stats['is_connected']}")
    
    print(f"\n🏆 Most Referenced Papers:")
    for paper_id, count in list(analysis['top_papers'].items())[:10]:
        paper = crawler.papers_by_id.get(paper_id, paper_id)
        print(f"   {count:3d} refs: {paper}")
    
    # Show centrality if available
    if 'centrality' in analysis:
        print(f"\n⭐ Most Central Papers (PageRank):")
        for paper_id, score in list(analysis['centrality']['pagerank'].items())[:5]:
            paper = crawler.papers_by_id.get(paper_id, paper_id)
            print(f"   {score:.4f}: {paper}")
    
    print(f"\n📈 Crawler Progress:")
    stats = analysis['crawler_stats']
    print(f"   Papers processed: {stats['papers_processed']}")
    print(f"   Citations found: {stats['citations_found']}")
    print(f"   API requests made: {stats['api_requests']}")
    
    if stats['start_time']:
        import time
        elapsed = time.time() - stats['start_time']
        print(f"   Runtime: {elapsed/60:.1f} minutes")


def compare_networks():
    """Compare citation network with Wikipedia network."""
    print("🔄 NETWORK COMPARISON: Citations vs Wikipedia")
    print("="*50)
    
    # Check if we have both networks
    citation_file = "./data/citation_crawler_state.pkl"
    wiki_file = "./data/crawler_state.pkl"
    
    citation_exists = os.path.exists(citation_file)
    wiki_exists = os.path.exists(wiki_file)
    
    print(f"Citation network: {'✅' if citation_exists else '❌'}")
    print(f"Wikipedia network: {'✅' if wiki_exists else '❌'}")
    
    if citation_exists:
        cite_manager = CiteManager()
        citation_crawler = IntelligentCitationCrawler(cite_manager)
        citation_analysis = citation_crawler.get_network_analysis()
        
        if 'error' not in citation_analysis:
            stats = citation_analysis['basic_stats']
            print(f"\n📚 Citation Network:")
            print(f"   Nodes: {stats['nodes']}")
            print(f"   Edges: {stats['edges']}")
            print(f"   Density: {stats['density']:.4f}")
    
    if wiki_exists:
        try:
            from flashcard.wiki_crawler import IntelligentWikiCrawler
            wiki_crawler = IntelligentWikiCrawler(filter_scientific=True)
            wiki_network = wiki_crawler.get_network_data()
            
            print(f"\n🌐 Wikipedia Network:")
            print(f"   Nodes: {len(wiki_network['flashcards'])}")
            print(f"   Edges: {len(wiki_network['connections'])}")
            
        except Exception as e:
            print(f"Error loading Wikipedia network: {e}")
    
    print(f"\n💡 Key Differences:")
    print(f"   📚 Citations: Academic papers, peer review, formal citations")
    print(f"   🌐 Wikipedia: Encyclopedic content, broader topics, hyperlinks")
    print(f"   🎯 Both: Knowledge networks, concept relationships, graph analysis")


def main():
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--explore', '-e']:
            explore_existing_network()
        elif sys.argv[1] in ['--compare', '-c']:
            compare_networks()
        else:
            print("Unknown option. Use --explore or --compare")
    else:
        demo_citation_crawler()


if __name__ == "__main__":
    main()