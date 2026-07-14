import PageHeader from "../components/common/PageHeader";
export default function ExtractRequirementsPage(){
 return <div className="stack-lg"><PageHeader eyebrow="Prepare" title="Extract requirements" description="Convert a source specification into the refined requirements file used by vPlan generation."/><section className="notice"><strong>Backend integration not present yet</strong><p>The current FastAPI application accepts an already-refined requirements JSON file. It does not yet expose the PDF or specification extraction workflow, so this page is prepared for that future endpoint without pretending the capability already exists.</p></section></div>;
}
