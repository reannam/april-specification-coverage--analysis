import { Link } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
export default function HomePage(){
 const cards=[
  ["Prepare requirements","Extract a structured requirements set from a specification.","/prepare/requirements"],
  ["Review requirement quality","Find ambiguous wording and conflicting statements.","/review/ambiguities"],
  ["Generate a vPlan","Create verification tests linked to requirements.","/verification/generate"],
  ["Check coverage","Assess mapping, traceability, testability and gaps.","/verification/coverage"]
 ];
 return <div className="stack-lg"><section className="hero"><PageHeader eyebrow="Verification planning workspace" title="From specification to reviewable vPlan." description="Prepare requirements, review their quality, generate tests and inspect coverage through one guided workflow." actions={<><Link className="button primary" to="/verification/generate">Generate vPlan</Link><Link className="button secondary" to="/prepare/requirements">Start from specification</Link></>}/></section>
 <section><div className="section-heading"><div><p className="eyebrow">Workflow</p><h2>Work through each stage</h2></div><p>Every generated output can be inspected in the browser and downloaded for engineering use.</p></div>
 <div className="workflow-grid">{cards.map(([t,d,p],i)=><Link className="workflow-card" to={p} key={p}><span>0{i+1}</span><h3>{t}</h3><p>{d}</p><strong>Open →</strong></Link>)}</div></section></div>
}
