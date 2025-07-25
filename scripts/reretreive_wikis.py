
import os

import json
import time
from flashcard.wikipedia import WikiManager

def explore_dict(dct, ntabs = 0):
    
    for k in dct:
        v = dct[k]
        if isinstance(v, dict):
            print('\t'*ntabs + k)
            return explore_dict(v, ntabs = ntabs + 1)
        else:
            print('\t'*(ntabs) + f"{k}: {v}")
        
def check_keys(dct, checkkey):
    
    res = None
    n = 0
    for k in dct:
        if k == checkkey:
            res = k
            n = len(dct[k])
        
        v = dct[k]
        if isinstance(v, dict):
            res, n = check_keys(v, checkkey)
        else:
            pass
        
        if res is not None:
            break
    
    return res, n
        

def main():
    
    wdir = "./data/wiki"
    wikis = os.listdir(wdir)
    
    wman = WikiManager()
    
    bads = list()
    for w in wikis:
        
        fn,ext = os.path.splitext(w)
        if not ext == '.json':
            continue
        
        data = wman.fetch_wikipedia_page(fn, overwrite = True)
        time.sleep(1.1)
        
        print(fn, list(data.keys()))

if __name__ == "__main__":
    main()