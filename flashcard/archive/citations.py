

import requests
import json
import networkx as nx
from time import time, sleep
import re
import numpy as np
import matplotlib.pyplot as plt

#%%


class CiteManager:  
    #manager
    
    valid = [200]
    
    call_frm = "https://api.opencitations.net/index/v2/{op}/{id}"
    key = "6388e468-f73e-44f0-a989-bb0892cd7ac8-1752419295"
    user_agent = 'grant-hobby/0.1'
    
    oci_ops = ['citation'] #must provide oci with this operation!!
    id_ops = ['citations', 'references', 'citation-count',
              'venue-citation-count','reference-count']
    
    field_names = ['oci', 'citing', 'cited', 'creation', 'timespan', 'journal_sc', 'author_sc']
    options = ['require','filter','sort','format','json']
    """ values and syntax for options:
    require=<field_name>
    filter=<field_name>:<operator><value>:
    sort=<order>(<field_name>):
    format=<format_type>: from 'csv','json'
    json=<operation_type>("<separator>",<field>,<new_field_1>,<new_field_2>,...):
    """
    
    default_options = {'format':'json'}
    
    rate_window = 10*60 #s
    rate_max = 0.9 #req/s
    min_wait = 1.1 #s
    
    def __init__(self,**kwargs):
        
        headers = self.make_headers(self.key, self.user_agent)
        self.sess = requests.Session()
        self.sess.headers.update(headers)
        
        self.nrequests = 0
        self.request_times = []
        self.requests_per_s = 0
        self.last_check = -1
    
    def get_citing(self, p, **options):
        
        citing = self.post_and_receive(self.id_ops[0], p, **options)
        p.set_nciting(len(citing))
        
        return citing
    
    def get_cited(self, p, **options):
                
        cited = self.post_and_receive(self.id_ops[1], p, **options)
        p.set_ncited(len(cited))
        
        return cited
    
    def post_and_receive(self, op, p, **options):
        
        tp, _id = p.get_typedid()
        
        options.update(self.default_options)
        call = self.build_request(op, tp, _id, **options)
        
        res = self._get(call)
        
        es = self.from_response(res.json())
        
        return es
    
    def _get(self, url):
        
        t0 = time()
        res = self.sess.get(url)
        t1 = time()
        dt = t1-t0
        t = int(t1)
        
        print(f'request took {dt:0.3f}s')
        
        sleep(max(self.min_wait - dt,0))
        
        if res.status_code in self.valid:
            # print(f'res returned valid!')
            
            if self.do_manage_rate():
                disp = self.manage_rate(t)
                
                if not disp:
                    print('oops, manage rate in _get failed')
        
        else:
            print(f'res returned invalid: {res.status_code}')
        
        return res
    
    def do_manage_rate(self):
        
        ##more complex behavior?
        # tnow = time()
        # if self.last_check - tnow > 100:
        #     return True
        # else:
        #     return False
        
        if self.nrequests % 5 == 0:
            return True
        else:
            return False
    
    def manage_rate(self, t):
        
        self.request_times.append(t)
        
        iclip = 0
        for rt in self.request_times:
            dt = max(t - rt, 0.001)
            if dt > self.rate_window:
                iclip += 1
            else:
                break
        new_request_times = self.request_times[iclip:]
        self.request_times = new_request_times
        
        self.nrequests = self.nrequests + 1 - iclip
        self.requests_per_s = self.nrequests / dt
        
        print(f'manage rate: nrq {self.nrequests}, rqts: {len(self.request_times)}, rq/s:{self.requests_per_s:0.3f}')
        
        while not self.check_rate():
            wait_time = 5 / self.rate_max
            sleep(wait_time)
            print(f'waiting for {wait_time:0.1}s to respect rate limits...')
        
        return True

        
    def check_rate(self):
        
        self.last_check = time()
        
        if len(self.request_times) < 5:
            return True
        
        if self.requests_per_s > self.rate_max:
            return False
        else:
            return True

    @classmethod
    def build_request(cls, op, idtype, idval, **options):
        
        idstr = cls.format_id(idtype, idval)
        call = cls.call_frm.format(op = op, id = idstr)
        call = cls.add_params(call, **options)
        
        return call
    
    @classmethod
    def get_count(cls, idtype, idval):
        
        if not idtype in cls.idtypes:
            
            return
        
        pass
    
    @classmethod
    def from_response(cls,reslist):
        
        outlist = []
        for d in reslist:
            
            p1 = paper.from_row(d['cited'])
            p2 = paper.from_row(d['citing'])
            ct = cite(d['oci'])
            
            outlist.append((ct, p1, p2))
        
        return outlist
        
    
    @staticmethod
    def make_headers(key, agent, **kwargs):
        
        headers = {'authorization':key, 'User-Agent':agent}
        for k in kwargs:
            if not k in headers:
                headers[k] = kwargs[k]
        
        return headers
    
    @staticmethod
    def add_params(url, **kwargs):
        
        paramstrs = []
        paramfrm = r'{k}={v}'
        
        for k, v in kwargs.items():
            
            paramstrs.append(paramfrm.format(k=str(k),v=str(v)))
            
        paramstr = '&'.join(paramstrs)
        
        return url + '?' + paramstr

    @staticmethod
    def format_id(idtype, idstr):
        
        id_option = f'{idtype}:{idstr}'
        
        return id_option

#%%

class cite_network(nx.DiGraph):
    
    #from citing to cited; p1 cites p2; p1 = citing, p2 = cited
    
    def __init__(self, cman, **kwargs):
        super().__init__()
        self.cman = cman
        self.pactive = []
        self.pdone = []
        self.nnodes = 0
        self.ndone = 0
        self.nedges = 0
        self.strength_func = lambda p:p.nciting
        self.mean_strength = 0
        self.top_strength = 0
        self.strat = kwargs.get('strategy','first')
        self.fuzz = kwargs.get('fuzz',10)
        self.maxdist = kwargs.get('maxdist', 3)
    
    def get_add_paper(self, p, do_citing = True, do_cited = True):
        
        newcites = []
        
        if do_cited:
            cited = self.cman.get_cited(p)
            newcites.extend(cited)
            
        if do_citing:
            citing = self.cman.get_citing(p)
            newcites.extend(citing)
            
        p.set_done()
        self.ndone += 1
        self.move_to_done(p)
        self.add_cites(newcites)

    def crawl(self, pseed, nmax = 100):
        
        n = 0
        nrepeat = 0
        p = pseed
        
        while n < nmax:
            
            self.get_add_paper(p)
            
            print(f'{n}: added {p} with strength {p.strength}')

            if n%10 == 0:
                self.update()
            
            p = self.pick_from_start()
            
            n += 1
        
    def pick_from_start(self):
        
        return self.pactive[0]
        
    def _pick_from_start(self, up = True):
        
        #start with a completed node
        try:
            ppicked = self.pick_from(iter(self.pdone), up = up)
        except:
            print('pick failed, defaulting to first')
            ppicked = self.pactive[0]
            
        return ppicked
    
    def pick_from(self, neighbs, up = True):
        
        if self.strat == 'first':
            #take the first one in the neighborhood
            p = next(neighbs)
            
        elif self.strat == 'fuzzy':
            #pick randomly biased towards top of dist, use as seed
            
            skip = int(np.abs(np.random.normal(loc = 0, scale = self.fuzz)))
            
            for n in skip:
                p = next(neighbs)
            
        else:
            #take the first from the list, randomly select from active nodes until 
            #one is within max distance
            
            p = next(neighbs)
            
            while True:
                i = np.random.randint(len(self.active))
                pi = self.pactive[i]
                dist = self.number_of_edges(p, pi)
                if dist <= self.maxdist:
                    break
                
            return pi
        
        if up:
            nf = self.predecessors
        else:
            nf = self.successors
            
        if p.done:
            return self.pick_from(nf(p), up = up)
        else:
            return p
    
    
    def set_strength_function(self, strfunc):
        
        self.strength_func = strfunc
        
    def update_strength(self):
        
        for p in self.pactive:
            st = self.strength(p)
            p.set_strength(st)
        
        self.pactive = list(sorted(self.pactive, key = lambda p:p.strength, reverse = True))
        
    def strength(self, p):
        
        return self.strength_func(p)
        
    def update_mean(self, p):
        
        newmean = (self.mean_strength * self.nnodes + p.strength) / (self.nnodes + 1)
        
        return newmean
        
    def update_metrics(self):
        
        mean_str = 0
        for p in self.pactive:
            
            nciting = self.in_degree(p)
            if nciting > 0:
                p.set_nciting(nciting)
            ncited = self.out_degree(p)
            if ncited > 0:
                p.set_ncited(ncited)
            
            st = self.strength(p)
            p.set_strenght(st)
            mean_str += st
            
        self.nnodes = len(self.pactive)
        mean_str /= self.nnodes
    
    def update(self):
        
        for p in self.nodes:
            st = self.strength(p)
            p.set_strength(st)
            
            if p.done:
                self.move_to_done(p)
            
        self.pdone = list(sorted(self.pdone, key = lambda p:p.strength, reverse = True)) 
        
        pass
    
    
    def move_to_done(self, p):
        
        st = self.strength(p)
        p.set_strength(st)
        
        if not p in self.pdone:
            print(f'moving to end of done ({len(self.pdone)}): {p}')
            self.pdone.append(p)
            # print(f'number done ({len(self.pdone)})')
                
        if p in self.pactive:
            self.pactive.remove(p)
    
    def add_paper(self, p1):
        
        if p1 in self.nodes:

            return
        
        self.add_node(p1)
        if p1.done:
            self.move_to_done(p1)
        else:
            self.pactive.append(p1)
        self.nnodes += 1
    
    def add_cite(self, ct, p1, p2):
        
        self.add_paper(p1)
        self.add_paper(p2)
        self.add_edge(p1, p2, ct = ct)
        self.nedges += 1
    
    def add_cites(self, ctp12list):
        
        for ct, p1, p2 in ctp12list:
            self.add_cite(ct, p1, p2)
            
        print(f'added {len(ctp12list)} new citations to network')
        
        
    def from_references(self, p1, p2cs):
        
        for p2, ct in p2cs:
            self.add_cite(ct, p1, p2)
            
        ncited = len(p2cs)
    
    def from_citations(self, p1cs, p2):
        
        for p1,ct in p1cs:
            self.add_cite(ct, p1, p2)
            
        nciting = len(p1cs)

    def draw(self):
        return nx.draw(self)

    def plot_strength(self):
        
        data = [p.strength for p in self.pdone]
        f = plt.plot(data)
        
        return f

#%%

class paper:
    
    _instances = {}
    
    idtypes = ['doi','omid','openalex','pmid','isbn']
    regex = {
        'doi':re.compile('(?:doi:)?(10\.\d{4,}/.+)', re.IGNORECASE),
        'omid':re.compile('(?:omid:)?(br/\d{9,12})'),
        'openalex':re.compile('(?:openalex:)?(W\d{7,10})'),
        'pmid':re.compile('(?:pmid:)?(\d{1,8})'),
        'isbn':re.compile('(?:isbn:)?(\d{13})'),
        }
    
    re_ndig = re.compile('(\d+)')
    
    n = 0
    ni = 0

    @classmethod
    def __new__(cls, *ids, **kwargs):
        
        good_typedids = {}
        
        for typ, _id in kwargs.items():
            if not isinstance(_id, str):
                continue
            
            if not typ in cls.idtypes:
                continue
            
            newid = cls._val_id(_id, typ)
            if newid and newid in cls._instances:
                ppr = cls._instances[newid]
                return ppr
            elif newid:
                good_typedids[typ] = _id
            else:
                pass
        
        for _id in ids:
            if not isinstance(_id, str):
                continue
            
            tp, newid = cls._val_ids(_id)
            if newid and newid in cls._instances:
                ppr = cls._instances[newid]
                return ppr
            elif newid:
                good_typedids[tp] = newid
            else:
                pass
        
        instance = super().__new__(cls)
        for typ,_id in good_typedids.items():
            setattr(instance, typ, _id)
            cls._instances[_id] = instance
            
        cls.ni = len(cls._instances)
        cls.n += 1
        
        return instance
    
    def __init__(self, *ids, **kwargs):
        
        if hasattr(self, '_initialized'):
            return
        
        self.nciting = kwargs.get('nciting', -1)
        self.ncited = kwargs.get('ncited', -1)
        self.strength = kwargs.get('strength', -1)
        self.done = False
        
        self._initialized = True
        
        for tp, _id in kwargs.items():
            if tp in self.idtypes:
                type(self)._instances[_id] = self

    def get_id(self, idtype = None):
        
        tp, _id = self.get_typedid(idtype = idtype)
        
        return _id
        

    def get_typedid(self, idtype = None):
        
        mylist = self.idtypes
        if idtype:
            mylist.insert(0, idtype)
        
        for tp in mylist:
            if hasattr(self, tp):
                return tp, getattr(self, tp)
        
        print('this shouldn\'t happen: paper has no valid idtypes!')
        return None, None
    
    def get_idtypes(self):
        
        outlist = []
        
        for tp in self.idtypes:
            if hasattr(self, tp):
                outlist.append(tp)
        return outlist
    def get_all_typedids(self):
        
        outlist = []
        
        for tp in self.idtypes:
            if hasattr(self, tp):
                tup = tp, getattr(self, tp)
                outlist.append(tup)
        return outlist
    
    def set_nciting(self,val):
        self.nciting = val
        
    def set_ncited(self,val):
        self.ncited = val
        
    def set_strength(self,val):
        self.strength = val
        
    def set_done(self):
        print(f'set to done: {self}')
        self.done = True
    
    def to_dict(self):
        
        outdict = {}
        
        for tp in self.idtypes:
            if hasattr(self, tp):
                outdict[tp] = getattr(self,tp)
                
        if self.nciting > 0:
            outdict['nciting'] = self.nciting
            
        if self.ncited > 0:
            outdict['ncited'] = self.ncited
            
        if hasattr(self,'done'):
            outdict['done'] = self.done
        else:
            outdict['done'] = False
        
        return outdict
    
    @classmethod
    def from_row(cls, row):
        
        tids =  row.split(' ')
        
        p = cls(*tids)
        
        return p
      
    @classmethod
    def get(cls, _id):
        return cls._instances.get(_id)
    
    @classmethod
    def _val_id(cls, _id, idtype):
        
        reres = cls.regex[idtype].fullmatch(_id)
        if reres:
            return reres.groups()[0]
        
        srch = cls.re_ndig.findall(_id)
        nds = [len(s) for s in srch]
        nd_str = ','.join(nds)
        
        print(f'invalid paper id does not match {idtype} form: {_id}')
        print(f'paper id has digit groups: {nd_str}')
        return False
            
    @classmethod
    def _val_ids(cls, _id):
        
        for idtype in cls.idtypes:
            reres = cls.regex[idtype].fullmatch(_id)
            
            if reres:
                return idtype, reres.groups()[0]
        
        srch = cls.re_ndig.findall(_id)
        nd_str = ','.join([str(len(s)) for s in srch])
        
        print(f'invalid paper id matches no forms: {_id}')
        print(f'paper id has digit groups: {nd_str}')
        return False,False
    
    def __str__(self):
        
        firstatt, firstval = self.get_typedid()
        
        outstrs = [f"{firstatt}:{firstval}"]
        if self.nciting:
            outstrs.append(f'nciting:{self.nciting}')
        if self.ncited:
            outstrs.append(f'ncited:{self.ncited}')
        if self.strength:
            outstrs.append(f'strength:{self.strength}')
        meat = ', '.join(outstrs)
        
        return f"paper({meat})"
    
    def __repr__(self):
        
        return str(self)
        
    def __hash__(self):
        
        return hash(self.get_id())
            
        print('this shouldnt happen! paper {self} failed hash due to no ids..')
        return 0


class cite:
    #like an edge
    _instances = {}
    
    oci_re = re.compile('\d{10}-\d{11}')
    
    @classmethod
    def _val_oci(cls, oci):
        
        res = cls.oci_re.match(oci)
        if res:
            return True
        else:
            return False
        
    def __new__(cls, oci):
        if oci in cls._instances:
            return cls._instances[oci]
        inst = super().__new__(cls)
        cls._instances[oci] = inst
        
        return inst
    
    def __init__(self, oci):
        if hasattr(self,'_initialized'):
            return
        self._initialized = True
        self.oci = oci
        
    def __eq__(self, other):
        return self.oci == other.oci

    def __getitem__(self, ind):
        pass
    
    def __str__(self):
        
        return f"cite({self.oci})"
    
    def __repr__(self):
        
        return f"cite({self.oci})"
    
    def __hash__(self):
        
        return hash(self.oci)
    
    


