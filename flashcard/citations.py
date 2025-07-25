import heapq
import json
import os
import time
import pickle
import requests
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, Counter
import re
from datetime import datetime

class CiteManager:
    """Manages API calls to OpenCitations."""
    
    def __init__(self):
        self.valid = [200]
        self.call_frm = "https://api.opencitations.net/index/v2/{op}/{id}"
        self.key = "6388e468-f73e-44f0-a989-bb0892cd7ac8-1752419295"
        self.user_agent = 'grant-hobby/0.1'
        
        self.oci_ops = ['citation']
        self.id_ops = ['citations', 'references', 'citation-count',
                      'venue-citation-count','reference-count']
        
        self.default_options = {'format':'json'}
        
        # Rate limiting
        self.rate_window = 10*60  # seconds
        self.rate_max = 0.9       # requests/second
        self.min_wait = 1.1       # seconds
        
        # Session setup
        headers = self.make_headers(self.key, self.user_agent)
        self.sess = requests.Session()
        self.sess.headers.update(headers)
        
        # Rate tracking
        self.nrequests = 0
        self.request_times = []
        self.requests_per_s = 0
        self.last_check = -1
    
    def get_citing_papers(self, paper, **options) -> List[Tuple]:
        """Get papers that cite this paper."""
        citing = self.post_and_receive(self.id_ops[0], paper, **options)
        paper.set_nciting(len(citing))
        return citing
    
    def get_cited_papers(self, paper, **options) -> List[Tuple]:
        """Get papers cited by this paper."""
        cited = self.post_and_receive(self.id_ops[1], paper, **options)
        paper.set_ncited(len(cited))
        return cited
    
    def post_and_receive(self, op, paper, **options):
        """Make API request and parse response."""
        tp, _id = paper.get_typedid()
        
        options.update(self.default_options)
        call = self.build_request(op, tp, _id, **options)
        
        res = self._get(call)
        
        if res.status_code in self.valid:
            citations = self.from_response(res.json())
            return citations
        else:
            print(f"API request failed with status {res.status_code}")
            return []
    
    def _get(self, url):
        """Make rate-limited GET request."""
        t0 = time.time()
        res = self.sess.get(url)
        t1 = time.time()
        dt = t1 - t0
        
        print(f'Request took {dt:0.3f}s')
        
        # Respect minimum wait time
        sleep_time = max(self.min_wait - dt, 0)
        if sleep_time > 0:
            time.sleep(sleep_time)
        
        # Manage rate limiting
        if self.nrequests % 5 == 0:
            self._manage_rate(int(t1))
        
        return res
    
    def _manage_rate(self, t):
        """Manage API rate limiting."""
        self.request_times.append(t)
        
        # Remove old requests outside the window
        cutoff_time = t - self.rate_window
        self.request_times = [rt for rt in self.request_times if rt > cutoff_time]
        
        self.nrequests = len(self.request_times)
        self.requests_per_s = self.nrequests / self.rate_window if self.rate_window > 0 else 0
        
        print(f'Rate: {self.nrequests} requests, {self.requests_per_s:.3f} req/s')
        
        # Wait if we're over the rate limit
        while self.requests_per_s > self.rate_max:
            wait_time = 5.0 / self.rate_max
            print(f'Rate limit hit, waiting {wait_time:.1f}s...')
            time.sleep(wait_time)
            
            # Recalculate after waiting
            current_time = time.time()
            cutoff_time = current_time - self.rate_window
            self.request_times = [rt for rt in self.request_times if rt > cutoff_time]
            self.nrequests = len(self.request_times)
            self.requests_per_s = self.nrequests / self.rate_window
    
    def build_request(self, op, idtype, idval, **options):
        """Build API request URL."""
        idstr = self.format_id(idtype, idval)
        call = self.call_frm.format(op=op, id=idstr)
        call = self.add_params(call, **options)
        return call
    
    @classmethod
    def from_response(cls, reslist):
        """Parse API response into citation objects."""
        outlist = []
        for d in reslist:
            try:
                p1 = Paper.from_row(d['cited'])
                p2 = Paper.from_row(d['citing'])
                ct = Citation(d['oci'])
                outlist.append((ct, p1, p2))
            except Exception as e:
                print(f"Error parsing citation: {e}")
                continue
        return outlist
    
    @staticmethod
    def make_headers(key, agent, **kwargs):
        """Create HTTP headers for API requests."""
        headers = {'authorization': key, 'User-Agent': agent}
        headers.update(kwargs)
        return headers
    
    @staticmethod
    def add_params(url, **kwargs):
        """Add query parameters to URL."""
        params = '&'.join(f'{k}={v}' for k, v in kwargs.items())
        return f'{url}?{params}' if params else url
    
    @staticmethod
    def format_id(idtype, idstr):
        """Format identifier for API."""
        return f'{idtype}:{idstr}'

class CrossRefManager:
    
    def __init__(self):
        self.call_frm = "https://api.crossref.org/works/{doi}"
        self.user_agent = 'grant-hobby/0.1'
        self.mailto = 'grant.tremel@proton.me'
        
        self.options = {
            'select':('title','author','published-print')   
        }
        
        self.keys = ['indexed', 'reference-count', 'publisher', 'issue', 'content-domain', 'short-container-title', 'published-print', 'DOI', 'type', 'created', 'page', 'source', 'is-referenced-by-count', 'title', 'prefix', 'volume', 'author', 'member', 'container-title', 'original-title', 'language', 'link', 'deposited', 'score', 'resource', 'subtitle', 'short-title', 'issued', 'references-count', 'journal-issue', 'URL', 'relation', 'ISSN', 'issn-type', 'subject', 'published']
        
        headers = {'User-Agent': self.user_agent,'mailto':self.mailto} #is this where mailto goes?
        self.sess = requests.Session()
        self.sess.headers.update(headers)
        
        self.rate_limit = 50 #requests/s
    
    
    def get(self, doi, take = ['title','author','issued']):

        call = self.build_request(doi)
        
        res = self.sess.get(call)
        if not res.status_code == 200:
            return {}
        
        msg = res.json()['message']
        
        if take:
            outdict = {k:msg.get(k) for k in take if k in self.keys}
        else:
            outdict = msg
            
        if 'title' in outdict:
            ttl = outdict.get('title')
            outdict['title'] = self.process_title(ttl)
        if 'author' in outdict:
            if outdict['author']:
                outdict['author'] = self.process_authors(outdict['author'])
        if 'issued' in outdict:
            outdict['issued'] = self.process_issued(outdict['issued'])
        
        return outdict
    
    def get_set(self, paper, take = ['title','author','issued']):
        
        doi = paper.get_id('doi')
        if not doi:
            return {}
        out = self.get(paper, take = take)
        paper.set_data(**out)
        
        return out
    
    def get_set_many(self, papers, take = ['title','author','issued'], delay = 0.1):
        
        for p in papers:
            self.get_set(p, take = take)
            
            time.sleep(delay)
        
    
    def build_request(self, doi, **options):
        
        optstrs = []
        opt_frm = '{k}={v}'
        
        for k in self.options:
            if k in options:
                v = options[k]
                if isinstance(v,str):
                    v = [v]
                
                vstr = ','.join(v)
                
                optstr = opt_frm.format(k=k, v=vstr)
                optstrs.append(optstr)
        
        opts = "&".join(optstrs)
        
        call = self.call_frm.format(doi=doi)
        req = "?".join((call,opts))
        
        return req
    
    def process_title(self, title):
        
        if not title:
            return ''
        if isinstance(title, list):
            title = title[0]
        
        return title
    
    def process_authors(self, authors):
        
        if not authors:
            return []
        
        outlist = []
        for a in authors:
            n1 = a.get('family', '')
            n2 = a.get('given','')
            
            if n1 or n2:
                authname = ', '.join((n1, n2))
            else:
                continue
            
            outlist.append(authname)
        
        return outlist
    
    def process_issued(self, issued):
        
        if not issued:
            return 0
        
        ymd = issued['date-parts'][0]
        if not ymd:
            return 0
        ymd = ymd + [1]*(3 - len(ymd))
        dtdict = dict(zip(['year','month','day'],ymd))
        return datetime(**dtdict).timestamp()

        
# Keep the existing Paper and Citation classes with minor improvements
class Paper:
    """Paper class with improved state management."""
    
    _instances = {}
    idtypes = ['doi','omid','openalex','pmid','isbn','arxiv']
    regex = {
        'doi': re.compile(r'(?:doi:)?(10\.\d{4,}/.+)', re.IGNORECASE),
        'omid': re.compile(r'(?:omid:)?(br/\d{6,12})'),
        'openalex': re.compile(r'(?:openalex:)?(W\d{6,10})'),
        'pmid': re.compile(r'(?:pmid:)?(\d{1,8})'),
        'isbn': re.compile(r'(?:isbn:)?(\d{10,13})'),
        'arxiv': re.compile(r'(?:arxiv:)?(?:([a-z-]+(?:\.[A-Z]{2})?/\d{7})|(\d{4}\.\d{4,5}(?:v\d+)?))(?:\s|$)', re.IGNORECASE)
    }
    # pmcid:PMC1188143
    
    doi_web_frm = 'https://doi.org/{doi}'
    
    n = 0
    ni = 0

    @classmethod
    def __new__(cls, *ids, **kwargs):
        # Same singleton logic as before
        good_typedids = {}
        
        for typ, _id in kwargs.items():
            if not isinstance(_id, str) or typ not in cls.idtypes:
                continue
            
            newid = cls._val_id(_id, typ)
            if newid and newid in cls._instances:
                return cls._instances[newid]
            elif newid:
                good_typedids[typ] = _id
        
        for _id in ids:
            if not isinstance(_id, str):
                continue
            
            tp, newid = cls._val_ids(_id)
            if newid and newid in cls._instances:
                return cls._instances[newid]
            elif newid:
                good_typedids[tp] = newid
        
        instance = super().__new__(cls)
        for typ, _id in good_typedids.items():
            setattr(instance, typ, _id)
            cls._instances[_id] = instance
            
        cls.ni = len(cls._instances)
        cls.n += 1
        
        return instance
    
    def __init__(self, *ids, **kwargs):
        if hasattr(self, '_initialized'):
            return
        
        self.title = ''
        self.authors = []
        self.issued_timestamp = 0
        
        self.nciting = kwargs.get('nciting', 0)
        self.ncited = kwargs.get('ncited', 0)
        self.strength = kwargs.get('strength', 0)
        self.done = False
        
        self._initialized = True
        
        for tp, _id in kwargs.items():
            if tp in self.idtypes:
                type(self)._instances[_id] = self

    def get_id(self, idtype=None):
        """Get the paper's ID."""
        tp, _id = self.get_typedid(idtype=idtype)
        return _id
        
    def get_typedid(self, idtype=None):
        """Get the paper's typed ID."""
        mylist = self.idtypes
        if idtype:
            mylist = [idtype] + mylist
        
        for tp in mylist:
            if hasattr(self, tp):
                return tp, getattr(self, tp)
        
        print('Paper has no valid idtypes!')
        return None, None
    
    def set_nciting(self, val):
        """Set number of citing papers."""
        self.nciting = val
        
    def set_ncited(self, val):
        """Set number of cited papers."""
        self.ncited = val
        
    def set_strength(self, val):
        """Set paper strength/priority."""
        self.strength = val
        
    def set_done(self):
        """Mark paper as processed."""
        self.done = True
    
    def set_data(self, **kwargs):
        self.title = kwargs.get('title','')
        self.authors = kwargs.get('authors',[])
        self.issued_timestamp = kwargs.get('issued',0)
    
    def to_dict(self):
        """Convert paper to dictionary."""
        outdict = {}
        
        for tp in self.idtypes:
            if hasattr(self, tp):
                outdict[tp] = getattr(self, tp)
                
        outdict.update({
            'nciting': self.nciting,
            'ncited': self.ncited,
            'strength': self.strength,
            'done': self.done
        })
        
        return outdict
    
    def open(self):
        doiid = self.get_id('doi')
        if doiid is None:
            return
        import subprocess
        browser = 'firefox'
        url = self.doi_web_frm.format(doi=doiid)
        
        subprocess.run([browser, url], check=False)
    
    @classmethod
    def from_row(cls, row):
        """Create paper from API response row."""
        tids = row.split(' ')
        return cls(*tids)
    
    @classmethod
    def _val_id(cls, _id, idtype):
        """Validate ID format."""
        if idtype not in cls.regex:
            return False
        
        match = cls.regex[idtype].fullmatch(_id)
        if match:
            return match.groups()[0]
        
        print(f'Invalid paper ID format for {idtype}: {_id}')
        return False
            
    @classmethod
    def _val_ids(cls, _id):
        """Validate and determine ID type."""
        for idtype in cls.idtypes:
            match = cls.regex[idtype].fullmatch(_id)
            if match:
                return idtype, match.groups()[0]
        
        print(f'Invalid paper ID format: {_id}')
        return False, False
    
    def __str__(self):
        firstatt, firstval = self.get_typedid()
        return f"Paper({firstatt}:{firstval})"
    
    def __repr__(self):
        return str(self)
        
    def __hash__(self):
        return hash(self.get_id())
    
    def __lt__(self, other):
        return self.strength < other.strength
    
    def __gt__(self, other):
        return self.strength > other.strength
    
    def __lte__(self, other):
        return not (self > other)
    
    def __gte__(self, other):
        return not (self < other)

class Citation:
    """Citation class (simplified from cite class)."""
    
    _instances = {}
    oci_re = re.compile(r'\d{10}-\d{11}')
    
    def __new__(cls, oci):
        if oci in cls._instances:
            return cls._instances[oci]
        inst = super().__new__(cls)
        cls._instances[oci] = inst
        return inst
    
    def __init__(self, oci):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.oci = oci
        
    def __str__(self):
        return f"Citation({self.oci})"
    
    def __repr__(self):
        return str(self)
    
    def __hash__(self):
        return hash(self.oci)



if __name__ == "__main__":
    pass