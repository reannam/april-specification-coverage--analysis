import { useMemo, useState } from "react";
export default function ReadableRecords({records,idKeys=["id"],empty="No records available."}:{records:Record<string,unknown>[];idKeys?:string[];empty?:string}) {
  const [query,setQuery]=useState("");
  const filtered=useMemo(()=>records.filter(r=>JSON.stringify(r).toLowerCase().includes(query.toLowerCase())),[records,query]);
  if(!records.length) return <div className="empty-state"><strong>No results</strong><p>{empty}</p></div>;
  return <div><div className="records-toolbar"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search results"/><span>{filtered.length} items</span></div>
    <div className="record-list">{filtered.map((r,i)=>{const id=idKeys.map(k=>r[k]).find(Boolean)??`Item ${i+1}`;return <article className="record-card" key={`${String(id)}-${i}`}><h3>{String(id)}</h3><dl>{Object.entries(r).map(([k,v])=><div key={k}><dt>{k.replaceAll("_"," ")}</dt><dd>{Array.isArray(v)?<ul>{v.map((x,j)=><li key={j}>{typeof x==="object"?JSON.stringify(x):String(x)}</li>)}</ul>:typeof v==="object"&&v!==null?<pre>{JSON.stringify(v,null,2)}</pre>:String(v??"Not provided")}</dd></div>)}</dl></article>})}</div>
  </div>;
}
