import PageHeader from "../components/common/PageHeader";
export default function InconsistenciesPage(){
 return <div className="stack-lg"><PageHeader eyebrow="Review" title="Compare specification versions" description="Compare two extracted specification versions and review changed, removed or conflicting requirements."/><section className="notice"><strong>Backend integration not present yet</strong><p>The uploaded backend currently exposes vPlan generation, edge-case analysis, weak-language analysis and coverage. It does not expose an inconsistency-check endpoint, so this page intentionally does not call an invented API.</p></section></div>;
}
