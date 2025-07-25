
from flashcard.wikipedia import WikiManager
from flashcard.citations import Paper, Citation, CiteManager, CrossRefManager
from flashcard.paper_database import PaperDatabase
from flashcard.crawler import Crawler
from flashcard.knowledge_database import WikiPage, WikiLink, CrossnetworkConnection, UnifiedDatabase, DOIExtractor


def main():
    
    dbpath = "./data/unified/knowledge_graph.db"
    
    db = UnifiedDatabase(dbpath)
    
    crawler = Crawler()
    pass

if __name__=='__main__':
    main()
    