import PageHeader from "../components/common/PageHeader";

export default function ExtractPdfPage() {
  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Prepare"
        title="Extract from PDF"
        description="Upload a source specification PDF and convert it into structured extraction data before refining requirements or selecting chapters."
      />

      <section className="notice">
        <strong>PDF extraction integration is not connected yet</strong>
        <p>
          This page is ready for the PDF extraction endpoint. Until that backend
          route is available, use an existing extracted JSON file in Extract
          requirements or Extract chapters.
        </p>
      </section>
    </div>
  );
}
