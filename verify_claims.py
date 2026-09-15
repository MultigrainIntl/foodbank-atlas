"""Verify every checkable factual claim on the methodology page against the
live map data and the build code. Prints PASS/FAIL per claim."""
import json, glob, os, re, sys, statistics as st, numpy as np

# Resolve the repo from this file's own location, so the script works from any directory.
REPO = os.path.dirname(os.path.abspath(__file__))
def load(p):
    t = open(p, encoding='utf-8').read(); i = t.find('const DATA=')
    if i < 0: return None
    s = t.index('{', i); d=0; j=s; ins=False; esc=False
    while j < len(t):
        c = t[j]
        if ins:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c=='"': ins=False
        elif c=='"': ins=True
        elif c in '{[': d+=1
        elif c in '}]':
            d-=1
            if d==0: j+=1; break
        j+=1
    return [x['properties'] for x in json.loads(t[s:j])['features']]

CA_IND = [('lim',False),('govt',False),('inc',True)]
US_IND = [('pov',False),('fpl200',False),('snap',False),('inc',True)]
maps = {}
for f in sorted(glob.glob(f'{REPO}/docs/*.html')):
    r = load(f)
    if r: maps[os.path.basename(f)[:-5]] = r
if not maps:
    sys.exit(f'no map pages found under {REPO}/docs -- nothing to verify')
ca = {k:v for k,v in maps.items() if 'dauid' in v[0]}
us = {k:v for k,v in maps.items() if 'dauid' not in v[0]}

def norm_cols(rows, IND, inbase):
    base = [r for r in rows if inbase(r)]
    mm = {}
    for k,_ in IND:
        v = [r[k] for r in base if r.get(k) is not None]
        mm[k] = (min(v), max(v)) if v else (0,1)
    return mm

def recompute(rows, IND, inbase):
    mm = norm_cols(rows, IND, inbase); out=[]
    for r in rows:
        parts=[]
        for k,inv in IND:
            x=r.get(k)
            if x is None: continue
            lo,hi=mm[k]; v=(x-lo)/((hi-lo) or 1)
            if inv: v=1-v
            parts.append(max(0.0,min(1.0,v)))
        out.append(round(100*sum(parts)/len(parts),1) if parts else None)
    return out

CAbase = lambda r: r.get('pop') and not r.get('sup')
USbase = lambda r: not r.get('gq') and r.get('pop')

R=[]
def chk(claim, ok, got=''):
    R.append((ok, claim, got))

# 1 formula reproduces every score
worst=0; nscored=0
for name,rows in maps.items():
    IND, base = (CA_IND, CAbase) if 'dauid' in rows[0] else (US_IND, USbase)
    pred = recompute(rows, IND, base)
    for r,p in zip(rows,pred):
        if r.get('score') is None or p is None:
            if r.get('score') != p: worst=999
            continue
        worst=max(worst,abs(p-r['score'])); nscored+=1
chk("formula reproduces every published score exactly", worst==0, f"worst diff {worst}, n={nscored:,}")
chk("page says 50,718 scored neighbourhoods", nscored==50718, f"actual {nscored:,}")

# counts
nca=sum(len(v) for v in ca.values()); nus=sum(len(v) for v in us.values())
ca_scored=sum(1 for v in ca.values() for x in v if x.get('score') is not None)
ca_unscored=nca-ca_scored
ca_partial=sum(1 for v in ca.values() for x in v if x.get('score') is not None and any(x.get(k) is None for k,_ in CA_IND))
us_scored=sum(1 for v in us.values() for x in v if x.get('score') is not None)
us_partial=sum(1 for v in us.values() for x in v if x.get('score') is not None and any(x.get(k) is None for k,_ in US_IND))
us_gq=sum(1 for v in us.values() for x in v if x.get('gq'))
chk("41 maps", len(maps)==41, f"{len(maps)}")
chk("Canada: 9 maps, 24,420 areas", len(ca)==9 and nca==24420, f"{len(ca)} maps, {nca:,}")
chk("Canada: 23,836 scored", ca_scored==23836, f"{ca_scored:,}")
chk("Canada: 584 unscored", ca_unscored==584, f"{ca_unscored}")
chk("Canada: 444 partial (1.9%)", ca_partial==444 and abs(100*ca_partial/ca_scored-1.9)<0.15, f"{ca_partial} = {100*ca_partial/ca_scored:.1f}%")
chk("US: 32 maps, 26,882 tracts, all scored", len(us)==32 and nus==26882 and us_scored==nus, f"{len(us)}, {nus:,}, scored {us_scored:,}")
chk("US: 186 partial (0.7%)", us_partial==186 and abs(100*us_partial/us_scored-0.7)<0.1, f"{us_partial} = {100*us_partial/us_scored:.1f}%")
chk("US: 555 group quarters", us_gq==555, f"{us_gq}")

# complete-case total
cc=0
for name,rows in maps.items():
    IND, base = (CA_IND, CAbase) if 'dauid' in rows[0] else (US_IND, USbase)
    cc += sum(1 for r in rows if base(r) and all(r.get(k) is not None for k,_ in IND))
chk("49,634 complete-indicator neighbourhoods", cc==49634, f"{cc:,}")

# peaks
def peak(n): return max(x['score'] for x in maps[n] if x.get('score') is not None)
chk("Saskatoon peak 95.3", peak('saskatoon')==95.3, str(peak('saskatoon')))
chk("Regina peak 95.7", peak('regina')==95.7, str(peak('regina')))
chk("Toronto peak 99.9", peak('toronto')==99.9, str(peak('toronto')))
top=max((x for x in maps['saskatoon'] if x.get('score') is not None), key=lambda x:x['score'])
chk("citation example: DA 47110567 = 95.3, Saskatoon's highest", top['dauid']=='47110567' and top['score']==95.3, f"{top['dauid']} @ {top['score']}")

# weights / PCA / stability
def stats(group, IND, base):
    W=[];sp=[];ve=[];loo=[];sing=[];jac=[]
    for name,rows in group.items():
        C=[r for r in rows if base(r) and all(r.get(k) is not None for k,_ in IND)]
        M=np.array([[float(r[k]) for k,_ in IND] for r in C])
        N=np.empty_like(M)
        for i,(k,inv) in enumerate(IND):
            c=M[:,i]; lo,hi=c.min(),c.max(); v=(c-lo)/((hi-lo) or 1)
            N[:,i]=1-v if inv else v
        N=np.clip(N,0,1); eq=N.mean(1)
        Z=(N-N.mean(0))/(N.std(0)+1e-12); Cm=np.corrcoef(Z,rowvar=False)
        w,v=np.linalg.eigh(Cm); pc=v[:,-1]
        if pc.sum()<0: pc=-pc
        wt=np.abs(pc)/np.abs(pc).sum(); W.append(wt); ve.append(w[-1]/w.sum())
        rk=lambda a: np.argsort(np.argsort(a)).astype(float)
        def sprm(a,b):
            a,b=rk(a)-rk(a).mean(),rk(b)-rk(b).mean()
            return float((a*b).sum()/np.sqrt((a**2).sum()*(b**2).sum()))
        sp.append(sprm(eq,N@wt))
        loo += [sprm(eq,np.delete(N,i,1).mean(1)) for i in range(N.shape[1])]
        sing += [sprm(eq,N[:,i]) for i in range(N.shape[1])]
        n=len(eq); tn=max(1,n//10); te=set(np.argsort(-eq)[:tn])
        rng=np.random.default_rng(7); js=[]
        for _ in range(500):
            rw=rng.dirichlet(np.ones(N.shape[1])); t=set(np.argsort(-(N@rw))[:tn])
            js.append(len(te&t)/len(te|t))
        jac.append((np.mean(js), np.percentile(js,5)))
    return np.array(W).mean(0), min(sp), np.mean(ve), (min(loo),max(loo)), min(sing), (np.mean([j[0] for j in jac]), min(j[1] for j in jac))

cw,csp,cve,cloo,csing,cj = stats(ca, CA_IND, CAbase)
uw,usp,uve,uloo,using,uj = stats(us, US_IND, USbase)
chk("CA data-derived weights 0.333/0.327/0.340", [round(x,3) for x in cw]==[0.333,0.327,0.340], str([round(x,3) for x in cw]))
chk("US data-derived weights 0.250/0.267/0.241/0.242", [round(x,3) for x in uw]==[0.250,0.267,0.241,0.242], str([round(x,3) for x in uw]))
chk("rank correlation equal vs data-weighted = 0.999 both", round(csp,3)==0.999 and round(usp,3)==0.999, f"CA {csp:.4f} US {usp:.4f}")
chk("variance explained 78% CA / 80% US", round(cve*100)==78 and round(uve*100)==80, f"CA {cve*100:.0f}% US {uve*100:.0f}%")
chk("leave-one-out 0.90-0.99 CA", 0.895<=cloo[0] and cloo[1]<=0.995, f"{cloo[0]:.3f}-{cloo[1]:.3f}")
chk("leave-one-out 0.96-1.00 US", 0.955<=uloo[0] and uloo[1]<=1.0, f"{uloo[0]:.3f}-{uloo[1]:.3f}")
chk("worst single indicator 0.66 CA", round(csing,2)==0.66, f"{csing:.3f}")
chk("worst single indicator 0.74 US", round(using,2)==0.74, f"{using:.3f}")
chk("500 weightings: about three quarters overlap", 0.70<=cj[0]<=0.80 and 0.70<=uj[0]<=0.82, f"CA {cj[0]:.2f} US {uj[0]:.2f}")
chk("worst cases about half", 0.40<=cj[1]<=0.55 and 0.40<=uj[1]<=0.55, f"CA {cj[1]:.2f} US {uj[1]:.2f}")

# code-level claims
src_ca=open(f'{REPO}/build_ca.py').read(); src_us=open(f'{REPO}/build_atlas.py').read()
chk("equal weights: code divides by count, no weight vector", 'sum(parts) / len(parts)' in src_ca and 'sum(parts) / len(parts)' in src_us)
chk("clamped to 0-1", 'max(0.0, min(1.0, n))' in src_ca and 'max(0.0, min(1.0, n))' in src_us)
chk("rounded to 1 decimal", 'round(100 * sum(parts) / len(parts), 1)' in src_ca)
chk("CA sup = lim and inc both missing", '"sup": (lim is None and inc is None)' in src_ca)
chk("US gq rule: pop<1200 or gq share>=0.5", "pop < 1200" in src_us and "(gqpop or 0) / pop >= 0.5" in src_us)
chk("CA codes 331/144/229", '"inc": 229' in src_ca and '"lim": 331' in src_ca and '"govt": 144' in src_ca)
chk("US tables B17001/C17002/B22003/B19013", all(t in src_us for t in ['B17001','C17002','B22003','B19013']))
chk("TIGER 2023 boundaries", 'tiger2023' in src_us)
chk("CA reference set excludes sup and zero pop", 'r["pop"] and not r["sup"]' in src_ca)
chk("US reference set excludes gq and zero pop", 'not r["gq"] and r["pop"]' in src_us)
tca=open(f'{REPO}/template_ca.html').read(); tus=open(f'{REPO}/template.html').read()
chk("CA suppressed drawn grey dashed", "dashArray:'4,4'" in tca and "#9aa8a2" in tca)
chk("US group quarters drawn purple dashed", "dashed var(--gq)" in tus)
chk("missing shown as a dash", "n==null?'—'" in tca)

# geography sizes
capop=[x['pop'] for v in ca.values() for x in v if x.get('pop')]
uspop=[x['pop'] for v in us.values() for x in v if x.get('pop')]
chk("DAs about 400-700 people", 400<=st.median(capop)<=700, f"median {st.median(capop):.0f}")
chk("tracts about 4,000 people", 3500<=st.median(uspop)<=4500, f"median {st.median(uspop):.0f}")

fails=[r for r in R if not r[0]]
for ok,claim,got in R:
    print(("  PASS  " if ok else "  FAIL  ")+claim+(f"   [{got}]" if got and not ok else ""))
print(f"\n{len(R)-len(fails)}/{len(R)} claims verified.")
if fails:
    print("\nFAILED:")
    for _,c,g in fails: print(f"  - {c}   actual: {g}")
sys.exit(1 if fails else 0)
