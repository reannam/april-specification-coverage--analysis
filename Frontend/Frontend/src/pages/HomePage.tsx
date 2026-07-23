import { Link } from "react-router-dom";

import PageHeader from "../components/common/PageHeader";

const workflowStages = [
  {
    title: "Extract everything",
    description:
      "Convert the complete source PDF into structured document JSON, including pages, sections, tables, references, and candidate requirements.",
    path: "/prepare/pdf",
  },
  {
    title: "Extract requirements",
    description:
      "Refine the complete extraction to the normative and behavioural content relevant to verification planning.",
    path: "/prepare/requirements",
  },
  {
    title: "Generate the vPlan",
    description:
      "Categorise related requirements and generate grounded verification intent, edge cases, and weak-language findings.",
    path: "/verification/generate",
  },
  {
    title: "Check coverage",
    description:
      "Re-evaluate the generated tests against the refined requirements and inspect final coverage evidence and gaps.",
    path: "/verification/coverage",
  },
];

export default function HomePage() {
  return (
    <div className="stack-lg">
      <section className="hero">
        <PageHeader
          eyebrow="Verification planning workspace"
          title="From complete specification to reviewable coverage."
          description="Follow the stages in order: extract the full specification, refine its vPlan-relevant requirements, generate the vPlan, then run coverage checks."
          actions={
            <>
              <Link className="button primary" to="/prepare/pdf">
                Start with PDF extraction
              </Link>
              <Link className="button secondary" to="/prepare/requirements">
                Use an existing extraction
              </Link>
            </>
          }
        />
      </section>

      <section>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Required workflow</p>
            <h2>Complete each stage in sequence</h2>
          </div>
          <p>
            Only the requirements-refinement stage prepares the input used by vPlan
            generation.
          </p>
        </div>
        <div className="workflow-grid">
          {workflowStages.map((stage, index) => (
            <Link className="workflow-card" to={stage.path} key={stage.path}>
              <span>0{index + 1}</span>
              <h3>{stage.title}</h3>
              <p>{stage.description}</p>
              <strong>Open →</strong>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
