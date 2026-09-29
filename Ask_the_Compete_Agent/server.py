import json, os, re, urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=Path(__file__).parent
DATA=json.loads((ROOT/'knowledge.json').read_text(encoding='utf-8'))
STOP=set('the a an and or for with from this that what where how does are is of to in on it its their they them you your our we have has had will would could should can may not more most less than across into about which who why today still all any some much many by as at'.split())

def tokens(s):
    return [t for t in re.findall(r'[a-z0-9]+', str(s).lower()) if len(t)>2 and t not in STOP]

def score(q, rec):
    ql=q.lower(); qt=set(tokens(q))
    text=' '.join(str(rec.get(k,'')) for k in ['Provider','Parameter','Sub-industry','Finding','Evidence Type','Rating','Rating Rationale','Source','Source Location','Search Tags'])
    tt=set(tokens(text)); s=len(qt & tt)
    for p in ['aws','gcp','anthropic','microsoft']:
        if p in ql and rec.get('Provider','').lower()==p: s+=5
    for sub in ['banking','capital markets','insurance']:
        if sub in ql and rec.get('Sub-industry','').lower()==sub: s+=4
    aliases={
        'workflow':'FSI Workflows and Agents','agent':'FSI Workflows and Agents','use case':'Priority Use Cases',
        'connector':'Data Ecosystem and Connectors','data':'Data Ecosystem and Connectors','mcp':'Data Ecosystem and Connectors','plugin':'Data Ecosystem and Connectors',
        'security':'Compliance, Governance, Security and Trust','governance':'Compliance, Governance, Security and Trust','compliance':'Compliance, Governance, Security and Trust','trust':'Compliance, Governance, Security and Trust',
        'partner':'Partner Ecosystem','ecosystem':'Partner Ecosystem','marketplace':'Marketplace','gtm':'GTM Execution','webinar':'GTM Execution','event':'GTM Execution','sales':'GTM Execution',
        'customer proof':'Customer References and Proof Points','customer reference':'Customer References and Proof Points','reference':'Customer References and Proof Points',
        'vertical':'Industry Solutions and FSI Verticalization','verticalization':'Industry Solutions and FSI Verticalization','product':'Industry Solutions and FSI Verticalization',
        'gap':'Customer Objections','objection':'Customer Objections','barrier':'Customer Objections'
    }
    for a,p in aliases.items():
        if a in ql and rec.get('Parameter','')==p: s+=4
    return s

def retrieve(q,n=14):
    ranked=sorted(((score(q,r),r) for r in DATA),key=lambda x:x[0],reverse=True)
    return [r for s,r in ranked[:n] if s>0]

def context(recs):
    chunks=[]
    for i,r in enumerate(recs,1):
        chunks.append(f"[{i}] {r['Provider']} | {r['Parameter']} | {r['Sub-industry']} | Rating={r['Rating']}\nFinding: {r['Finding']}\nRationale: {r['Rating Rationale']}\nSource: {r['Source']} | {r['Source Location']}")
    return '\n\n'.join(chunks)

SYSTEM="""You are Ask the Compete, an internal FSI AI competitive intelligence assistant.

Answer ONLY from the approved retrieved evidence. Do not use general knowledge. Do not invent facts. If evidence is insufficient, say so clearly.
The knowledge base covers AWS, GCP, Anthropic and Microsoft across 10 FSI competitive parameters and Banking, Capital Markets and Insurance.
Keep answers client-ready, simple, and concise. For comparisons, explain the key differences and do not claim more than the evidence supports.
Use inline citations [1], [2] tied to the supplied evidence. End with a compact Sources line.
For Customer Objections, High means fewer / better-mitigated barriers and Low means more material unresolved barriers.
"""

def offline(q,recs):
    if not recs:
        return ('No supporting evidence found in the approved knowledge base for that question.',[])
    bullets=[]
    for r in recs[:8]:
        bullets.append(f"- **{r['Provider']} — {r['Sub-industry']} ({r['Parameter']}):** {r['Finding']} ({r['Rating']}).")
    return ('Demo retrieval mode — set GEMINI_API_KEY for AI synthesis.\n\n'+'\n'.join(bullets), recs[:8])

def ai(q,history,recs):
    key=os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not key: return offline(q,recs)+(False,)
    model=os.getenv('GEMINI_MODEL','gemini-2.5-flash')
    hist='\n'.join([f"{h.get('role','user')}: {h.get('content','')}" for h in history[-6:]])
    prompt=f"RECENT CONVERSATION:\n{hist}\n\nAPPROVED EVIDENCE:\n{context(recs)}\n\nUSER QUESTION:\n{q}"
    payload={'systemInstruction':{'parts':[{'text':SYSTEM}]},'contents':[{'role':'user','parts':[{'text':prompt}]}],'generationConfig':{'temperature':0.1,'maxOutputTokens':1500}}
    req=urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',data=json.dumps(payload).encode(),headers={'x-goog-api-key':key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=45) as resp: data=json.loads(resp.read().decode())
        out=''.join(p.get('text','') for c in data.get('candidates',[])[:1] for p in c.get('content',{}).get('parts',[]))
        return (out or 'No answer returned.',recs,True)
    except Exception as e:
        return (f'AI synthesis failed ({type(e).__name__}); showing grounded retrieval instead.',recs,False)

class Handler(BaseHTTPRequestHandler):
    def send(self,code,obj,ctype='application/json'):
        body=obj if isinstance(obj,(bytes,bytearray)) else (json.dumps(obj).encode() if ctype.startswith('application/json') else str(obj).encode())
        self.send_response(code); self.send_header('Content-Type',ctype+'; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path in ['/','/index.html']:
            self.send(200,(ROOT/'index.html').read_text(encoding='utf-8'), 'text/html')
        elif self.path=='/api/status': self.send(200,{'records':len(DATA),'ai_enabled':bool(os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY'))})
        else: self.send(404,{'error':'Not found'})
    def do_POST(self):
        if self.path!='/api/chat': self.send(404,{'error':'Not found'}); return
        n=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(n).decode())
        q=str(payload.get('question','')).strip(); history=payload.get('history') or []
        if not q: self.send(400,{'error':'Question required'}); return
        recs=retrieve(q)
        answer,cited,enabled=ai(q,history,recs)
        self.send(200,{'answer':answer,'evidence':cited,'ai_enabled':enabled})
    def log_message(self,*args): pass

if __name__=='__main__':
    port=int(os.getenv('PORT','8787')); print(f'Ask the Compete: http://localhost:{port} | AI enabled={bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))}')
    ThreadingHTTPServer((os.getenv('HOST','0.0.0.0'),port),Handler).serve_forever()
