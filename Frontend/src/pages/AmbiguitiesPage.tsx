import PageHeader from "../components/common/PageHeader";

export default function AmbiguitiesPage() {
  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Review"
        title="Check for Inconsistencies"
        description="Review broader specification quality findings outside the core vPlan workflow."
      />

      <section className="notice unused-notice">
        <span className="pill">Unused</span>
        <strong>Ambiguity analysis is currently outside this vPlan workflow</strong>
        <p>
          The weak-language findings generated with the vPlan remain available under
          Verification → Weak language. They are not treated as the separate ambiguity-analysis flow.
        </p>
      </section>
    </div>
  );
}
