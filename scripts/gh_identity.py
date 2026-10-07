#!/usr/bin/env python3
"""gh_identity: stdlib-only GitHub operations with gh-first/urllib fallback."""
from __future__ import annotations
import argparse,json,os,re,shutil,subprocess,sys,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timezone
API="https://api.github.com"; REPO=re.compile(r"^[\w.-]+/[\w.-]+$")
class Error(RuntimeError):
 def __init__(self,code,uncertain=False): super().__init__(code); self.code=code; self.uncertain=uncertain
def now(): return datetime.now(timezone.utc).isoformat()
def repo(x):
 if not isinstance(x,str) or not REPO.fullmatch(x): raise ValueError("repo must be OWNER/REPO")
 return x
def token(): return os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
def gh_available(): return shutil.which("gh") is not None
def _gh(method,path,payload=None,timeout=30,mutating=False):
 env=os.environ.copy(); env.update(GH_PROMPT_DISABLED="1",GH_PAGER="cat"); env.pop("GH_REPO",None)
 a=["gh","api","--method",method,path]+(["--input","-"] if payload is not None else [])
 try:p=subprocess.run(a,input=json.dumps(payload) if payload is not None else None,capture_output=True,text=True,encoding="utf-8",timeout=timeout,env=env)
 except FileNotFoundError as e: raise Error("gh_not_found") from e
 except subprocess.TimeoutExpired as e: raise Error("timeout",mutating) from e
 except OSError as e: raise Error("process_error",mutating) from e
 if p.returncode:
  s=(p.stderr or p.stdout).lower()
  c="authentication_required" if p.returncode==4 else "cancelled" if p.returncode==2 else "gh_failed"
  if "http 403" in s:c="permission_or_rate_limit"
  if "http 404" in s:c="not_found_or_inaccessible"
  raise Error(c,mutating and ("http 5" in s or "timed out" in s))
 if not p.stdout.strip(): return None
 try:return json.loads(p.stdout)
 except json.JSONDecodeError as e: raise Error("invalid_json",mutating) from e
def _url(method,path,payload=None,timeout=30,mutating=False):
 h={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"gh_identity/0.1"}
 if token():h["Authorization"]="Bearer "+token()
 data=None if payload is None else json.dumps(payload).encode()
 q=urllib.request.Request(API+"/"+path.lstrip("/"),data=data,headers=h,method=method)
 try:
  with urllib.request.urlopen(q,timeout=timeout) as r: raw=r.read()
 except urllib.error.HTTPError as e:
  raise Error({401:"authentication_required",403:"permission_or_rate_limit",404:"not_found_or_inaccessible",422:"rejected"}.get(e.code,"http_error"),mutating and e.code>=500) from e
 except (urllib.error.URLError,TimeoutError,OSError) as e: raise Error("transport_error",mutating) from e
 if not raw:return None
 try:return json.loads(raw.decode())
 except (UnicodeError,json.JSONDecodeError) as e: raise Error("invalid_json",mutating) from e
def request(method,path,payload=None,transport="auto",timeout=30,mutating=False):
 if transport not in ("auto","gh","urllib"):raise ValueError("bad transport")
 if transport=="gh" or (transport=="auto" and gh_available()):
  try:return _gh(method,path,payload,timeout,mutating)
  except Error as e:
   if transport=="gh" or e.code not in ("gh_not_found","authentication_required"):raise
 return _url(method,path,payload,timeout,mutating)
def pages(path,transport="auto",timeout=30):
 out=[]; p=1; sep="&" if "?" in path else "?"
 while True:
  x=request("GET",f"{path}{sep}per_page=100&page={p}",transport=transport,timeout=timeout)
  if not isinstance(x,list):raise Error("invalid_json")
  out+=x
  if len(x)<100:return out
  p+=1
def capabilities():
 return {"schema":"gh-identity-capabilities/1","observed_at":now(),"python":sys.version.split()[0],"gh":gh_available(),"git":shutil.which("git") is not None,"token_present":bool(token())}
def repository(r,**k):
 r=repo(r);d=request("GET",f"repos/{r}",**k)
 return {"schema":"gh-identity-repository/1","repository":r,"id":d.get("id"),"default_branch":d.get("default_branch"),"visibility":d.get("visibility"),"archived":d.get("archived"),"url":d.get("html_url"),"observed_at":now()}
def repositories(owner,transport="auto",timeout=30):
 xs=pages(f"users/{owner}/repos?sort=full_name",transport,timeout)
 rows=[{"full_name":x.get("full_name"),"archived":x.get("archived"),"updated_at":x.get("updated_at"),"url":x.get("html_url")} for x in xs]
 return {"schema":"gh-identity-repositories/1","owner":owner,"complete":True,"count":len(rows),"repositories":rows}
def pr(r,n,**k):
 r=repo(r);d=request("GET",f"repos/{r}/pulls/{n}",**k)
 return {"schema":"gh-identity-pr/1","repository":r,"number":n,"state":d.get("state"),"draft":d.get("draft"),"merged":d.get("merged"),"mergeable":d.get("mergeable"),"head_sha":(d.get("head")or{}).get("sha"),"head_ref":(d.get("head")or{}).get("ref"),"base_sha":(d.get("base")or{}).get("sha"),"base_ref":(d.get("base")or{}).get("ref"),"url":d.get("html_url"),"observed_at":now()}
def comments(r,n,last=None,transport="auto",timeout=30):
 r=repo(r);xs=pages(f"repos/{r}/issues/{n}/comments",transport,timeout)
 ds=[{"id":x.get("id"),"author":(x.get("user")or{}).get("login"),"created_at":x.get("created_at"),"chars":len(x.get("body")or""),"preview":re.sub(r"\s+"," ",x.get("body")or"")[:240],"url":x.get("html_url")} for x in xs]
 if last is not None:ds=ds[-last:]
 return {"schema":"gh-identity-comments/1","repository":r,"number":n,"total":len(xs),"shown":len(ds),"complete":True,"comments":ds}
def reviews(r,n,transport="auto",timeout=30):
 r=repo(r);xs=pages(f"repos/{r}/pulls/{n}/reviews",transport,timeout)
 ds=[{"id":x.get("id"),"author":(x.get("user")or{}).get("login"),"state":x.get("state"),"commit_id":x.get("commit_id"),"submitted_at":x.get("submitted_at"),"chars":len(x.get("body")or"")} for x in xs]
 return {"schema":"gh-identity-reviews/1","repository":r,"number":n,"count":len(ds),"complete":True,"reviews":ds}
def runs(r,limit=20,transport="auto",timeout=30):
 r=repo(r);d=request("GET",f"repos/{r}/actions/runs?per_page={min(100,max(1,limit))}",transport=transport,timeout=timeout)
 ds=[{"run_id":x.get("id"),"attempt":x.get("run_attempt"),"status":x.get("status"),"conclusion":x.get("conclusion"),"head_sha":x.get("head_sha"),"event":x.get("event"),"url":x.get("html_url")} for x in (d.get("workflow_runs")or[])[:limit]]
 return {"schema":"gh-identity-runs/1","repository":r,"runs":ds}
def variable(r,name,transport="auto",timeout=30):
 r=repo(r);d=request("GET",f"repos/{r}/actions/variables/{urllib.parse.quote(name,safe='')}",transport=transport,timeout=timeout)
 return {"schema":"gh-identity-variable/1","repository":r,"name":d.get("name"),"value":d.get("value"),"updated_at":d.get("updated_at")}
def set_variable(r,name,value,write=False,transport="auto",timeout=30):
 r=repo(r);out={"schema":"gh-identity-variable-write/1","repository":r,"name":name,"status":"planned","mutation_status":"not_attempted","verification_status":"not_attempted"}
 if not write:return out
 try:
  try:request("PATCH",f"repos/{r}/actions/variables/{urllib.parse.quote(name,safe='')}",{"name":name,"value":value},transport,timeout,True)
  except Error as e:
   if e.code!="not_found_or_inaccessible":raise
   request("POST",f"repos/{r}/actions/variables",{"name":name,"value":value},transport,timeout,True)
 except Error as e:
  out.update(status="mutation_uncertain" if e.uncertain else "mutation_failed",mutation_status="uncertain" if e.uncertain else "failed",error=e.code)
  return out
 out["mutation_status"]="succeeded"
 try:
  got=variable(r,name,transport,timeout)
 except Error as e:
  out.update(status="verification_failed",verification_status="failed",verification_error=e.code)
  return out
 out["verified"]=got.get("value")==value
 out["verification_status"]="verified" if out["verified"] else "mismatch"
 out["status"]="verified" if out["verified"] else "verification_mismatch"
 return out

def post_comment(r,n,body,write=False,marker=None,transport="auto",timeout=30,sanitize_mentions=False):
 r=repo(r)
 if not body.strip():raise ValueError("empty body")
 if re.search(r"(^|[^A-Za-z0-9_])@[A-Za-z0-9_-]+",body):
  if sanitize_mentions:body=re.sub(r"(^|[^A-Za-z0-9_])@(?=[A-Za-z0-9_-]+)",lambda m:m.group(1)+"＠",body)
  else:raise ValueError("comment contains an active mention")
 if write and not marker:raise ValueError("marker is required for comment writes")
 if marker:
  if not re.fullmatch(r"<!-- gh-identity:[A-Za-z0-9_.:-]+ -->",marker):raise ValueError("invalid marker")
  for x in pages(f"repos/{r}/issues/{n}/comments",transport,timeout):
   if marker in (x.get("body")or""):return {"schema":"gh-identity-comment-write/1","status":"already_exists","id":x.get("id"),"url":x.get("html_url"),"marker":marker}
  body=marker+"\\n"+body
 if not write:return {"schema":"gh-identity-comment-write/1","status":"planned","chars":len(body),"marker":marker,"body":body}
 try:
  d=request("POST",f"repos/{r}/issues/{n}/comments",{"body":body},transport,timeout,True)
  return {"schema":"gh-identity-comment-write/1","status":"verified","id":d.get("id"),"url":d.get("html_url"),"marker":marker}
 except Error as e:return {"schema":"gh-identity-comment-write/1","status":"mutation_uncertain" if e.uncertain else "mutation_failed","error":e.code,"marker":marker}

def resolve_ref(r,ref,transport="auto",timeout=30):
 r=repo(r);d=request("GET",f"repos/{r}/commits/{urllib.parse.quote(ref,safe='')}",transport=transport,timeout=timeout)
 sha=d.get("sha") if isinstance(d,dict) else None
 if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-fA-F]{40}",sha):raise Error("invalid_commit")
 return {"schema":"gh-identity-ref/1","repository":r,"ref":ref,"sha":sha.lower(),"observed_at":now()}
def _min_checks(value):
 if not isinstance(value,int) or isinstance(value,bool) or value<1:raise ValueError("min_checks must be at least 1")
 return value

def summarize_checks(rows,expected_count,min_checks=1):
 min_checks=_min_checks(min_checks)
 if not isinstance(rows,list):raise ValueError("check rows must be a list")
 normalized=[{"id":x.get("id"),"name":x.get("name"),"status":x.get("status"),"conclusion":x.get("conclusion"),"url":x.get("url") or x.get("html_url"),"annotations_count":x.get("annotations_count",(x.get("output")or{}).get("annotations_count",0))} for x in rows]
 complete=isinstance(expected_count,int) and not isinstance(expected_count,bool) and expected_count==len(normalized)
 bad={"failure","cancelled","timed_out","action_required","startup_failure","stale"}
 if not complete:state="incomplete"
 elif len(normalized)<min_checks:state="pending"
 elif any(x["status"]!="completed" for x in normalized):state="pending"
 elif any(x["conclusion"] in bad for x in normalized):state="failed"
 elif not any(x["conclusion"]=="success" for x in normalized):state="failed"
 else:state="green"
 return {"state":state,"complete":complete,"expected_count":expected_count,"count":len(normalized),"min_checks":min_checks,"checks":normalized}

def checks_for_sha(r,sha,min_checks=1,transport="auto",timeout=30):
 min_checks=_min_checks(min_checks)
 r=repo(r);rows=[];page=1;expected=None
 while True:
  d=request("GET",f"repos/{r}/commits/{sha}/check-runs?per_page=100&page={page}",transport=transport,timeout=timeout)
  if not isinstance(d,dict) or not isinstance(d.get("check_runs"),list):raise Error("invalid_json")
  if expected is None:expected=d.get("total_count")
  rows += d["check_runs"]
  if len(d["check_runs"])<100:break
  page+=1
 summary=summarize_checks(rows,expected,min_checks)
 return {"schema":"gh-identity-checks/1","repository":r,"sha":sha,**summary,"observed_at":now()}

def observe_pr(r,n,min_checks=1,transport="auto",timeout=30):
 before=pr(r,n,transport=transport,timeout=timeout)
 ch=checks_for_sha(r,before["head_sha"],min_checks,transport,timeout)
 cs=comments(r,n,transport=transport,timeout=timeout)
 rs=reviews(r,n,transport=transport,timeout=timeout)
 after=pr(r,n,transport=transport,timeout=timeout)
 return {"schema":"gh-identity-pr-observation/1","repository":repo(r),"number":n,"head_sha":before["head_sha"],"base_sha":before["base_sha"],
  "state":before["state"],"draft":before["draft"],"mergeable":before["mergeable"],"checks":ch,"conversation":cs,"reviews":rs,
  "stale":before["head_sha"]!=after["head_sha"],"head_sha_after":after["head_sha"],"observed_at":now()}
def workflow(r,w,transport="auto",timeout=30):
 r=repo(r);d=request("GET",f"repos/{r}/actions/workflows/{urllib.parse.quote(str(w),safe='')}",transport=transport,timeout=timeout)
 return {"schema":"gh-identity-workflow/1","repository":r,"id":d.get("id"),"name":d.get("name"),"path":d.get("path"),"state":d.get("state"),"url":d.get("html_url"),"observed_at":now()}
def gh_help(*parts,timeout=15):
 if not gh_available():raise Error("gh_not_found")
 env=os.environ.copy();env.update(GH_PROMPT_DISABLED="1",GH_PAGER="cat");env.pop("GH_REPO",None)
 try:p=subprocess.run(["gh","help",*parts],capture_output=True,text=True,encoding="utf-8",timeout=timeout,env=env)
 except OSError as e:raise Error("process_error") from e
 if p.returncode:raise Error("gh_failed")
 return p.stdout

def local_identity(*,cwd=None,identity=None,env=None):
 env=os.environ if env is None else env
 if identity is not None:
  sha=identity.get("sha")
  if sha is not None and not re.fullmatch(r"[0-9a-fA-F]{40}",str(sha)):raise ValueError("invalid local sha")
  return {"schema":"gh-identity-local/1","sha":str(sha).lower() if sha else None,"ref":identity.get("ref"),"dirty":identity.get("dirty"),"source":identity.get("source","provided"),"observed_at":now()}
 sha=env.get("GITHUB_SHA")
 ref=env.get("GITHUB_HEAD_REF") or env.get("GITHUB_REF_NAME")
 if sha and re.fullmatch(r"[0-9a-fA-F]{40}",sha):
  return {"schema":"gh-identity-local/1","sha":sha.lower(),"ref":ref,"dirty":None,"source":"github-env","observed_at":now()}
 if shutil.which("git") is None:
  return {"schema":"gh-identity-local/1","sha":None,"ref":None,"dirty":None,"source":"unavailable","observed_at":now()}
 root=cwd or os.getcwd()
 def git(*args):
  p=subprocess.run(["git",*args],cwd=root,capture_output=True,text=True,encoding="utf-8",check=False)
  if p.returncode:raise Error("git_failed")
  return p.stdout.strip()
 sha=git("rev-parse","HEAD")
 if not re.fullmatch(r"[0-9a-fA-F]{40}",sha):raise Error("invalid_commit")
 ref=git("branch","--show-current") or None
 dirty=bool(git("status","--porcelain"))
 return {"schema":"gh-identity-local/1","sha":sha.lower(),"ref":ref,"dirty":dirty,"source":"git","observed_at":now()}

def compare_sha(local,remote_sha):
 lsha=local.get("sha") if isinstance(local,dict) else None
 lsha=str(lsha).lower() if lsha else None
 rsha=str(remote_sha).lower() if remote_sha else None
 return {"schema":"gh-identity-comparison/1","local_sha":lsha,"remote_sha":rsha,"comparable":bool(lsha and rsha),"same":(lsha==rsha) if lsha and rsha else None,"observed_at":now()}

def main(argv=None):
 argv=list(sys.argv[1:] if argv is None else argv)
 transport="auto"
 if "--transport" in argv:
  i=argv.index("--transport")
  if i+1>=len(argv): print(json.dumps({"status":"error","error":"invalid_argument"}),file=sys.stderr);return 2
  transport=argv[i+1]
  if transport not in ("auto","gh","urllib"): print(json.dumps({"status":"error","error":"invalid_argument"}),file=sys.stderr);return 2
  del argv[i:i+2]
 a=argparse.ArgumentParser();s=a.add_subparsers(dest="cmd",required=True)
 s.add_parser("capabilities")
 x=s.add_parser("repo");x.add_argument("repo")
 x=s.add_parser("repos");x.add_argument("owner")
 x=s.add_parser("pr");x.add_argument("repo");x.add_argument("number",type=int)
 x=s.add_parser("comments");x.add_argument("repo");x.add_argument("number",type=int)
 x=s.add_parser("reviews");x.add_argument("repo");x.add_argument("number",type=int)
 x=s.add_parser("runs");x.add_argument("repo")
 x=s.add_parser("variable-get");x.add_argument("repo");x.add_argument("name")
 x=s.add_parser("variable-set");x.add_argument("repo");x.add_argument("name");x.add_argument("value");x.add_argument("--write",action="store_true")
 x=s.add_parser("comment");x.add_argument("repo");x.add_argument("number",type=int);x.add_argument("body");x.add_argument("--operation-key");x.add_argument("--sanitize-mentions",action="store_true");x.add_argument("--write",action="store_true")
 try:ns=a.parse_args(argv)
 except SystemExit as e:return int(e.code)
 try:
  if ns.cmd=="capabilities":o=capabilities()
  elif ns.cmd=="repo":o=repository(ns.repo,transport=transport)
  elif ns.cmd=="repos":o=repositories(ns.owner,transport=transport)
  elif ns.cmd=="pr":o=pr(ns.repo,ns.number,transport=transport)
  elif ns.cmd=="comments":o=comments(ns.repo,ns.number,transport=transport)
  elif ns.cmd=="reviews":o=reviews(ns.repo,ns.number,transport=transport)
  elif ns.cmd=="runs":o=runs(ns.repo,transport=transport)
  elif ns.cmd=="variable-get":o=variable(ns.repo,ns.name,transport=transport)
  elif ns.cmd=="variable-set":o=set_variable(ns.repo,ns.name,ns.value,ns.write,transport)
  else:
   marker=f"<!-- gh-identity:{ns.operation_key} -->" if ns.operation_key else None
   o=post_comment(ns.repo,ns.number,ns.body,ns.write,marker,transport,sanitize_mentions=ns.sanitize_mentions)
 except (ValueError,Error) as e:print(json.dumps({"status":"error","error":getattr(e,"code","invalid_argument")}),file=sys.stderr);return 2
 print(json.dumps(o,ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
