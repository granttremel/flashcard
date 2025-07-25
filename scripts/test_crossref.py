
from flashcard.citations import IntelligentCitationCrawler, CiteManager, CrossRefManager, Paper
import json
import os

from pprint import pprint


def main():
    cite_manager = CiteManager()
    crawler = IntelligentCitationCrawler(
        cite_manager,
        data_dir="./data/citations",
        state_file="./data/citation_crawler_state_1.pkl"
    )
    
    # testpaper = crawler.priority_queue[0][2]
    testpaper = Paper(doi="10.1007/978-3-031-07696-1_5")
    
    crman = CrossRefManager()
    res = crman.get(testpaper, take = ['title','author','issued'])
    print(res)


if __name__ == "__main__":
    main()