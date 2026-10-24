import json,urllib.request
u='https://api-contract.weex.com/capi/v3/market/ticker/24hr'
r=urllib.request.Request(u,headers={'User-Agent':'WEEX-scanner-smoke/1.0','Accept':'application/json'})
x=json.loads(urllib.request.urlopen(r,timeout=30).read().decode())
rows=x if isinstance(x,list) else x.get('data',[])
print(json.dumps({'ok':bool(rows),'symbols':len(rows)}))
if not rows:raise SystemExit(2)
