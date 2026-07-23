import { useMemo, useState } from "react";

import FileUpload from "../components/common/FileUpload";
import PageHeader from "../components/common/PageHeader";
import {
  cleanSourceFilename,
  extractRecords,
  requirementIdOf,
  requirementTextOf,
  sourceSectionOf,
  type JsonRecord,
} from "../utils/formatters";

const chapterOf = (section: string) => {
  const match = section.toUpperCase().match(/^([A-Z]+\d+)/);
  return match?.[1] ?? section;
};

const belongsToChapter = (section: string, chapter: string) => {
  const normalisedSection = section.toUpperCase();
  const normalisedChapter = chapter.toUpperCase();

  return (
    normalisedSection === normalisedChapter ||
    normalisedSection.startsWith(`${normalisedChapter}.`)
  );
};

export default function ExtractChaptersPage() {
  const [file, setFile] = useState<File | null>(null);
  const [data, setData] = useState<unknown>(null);
  const [chapter, setChapter] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const load = async (nextFile: File | null) => {
    setFile(nextFile);
    setChapter("");
    setQuery("");
    setError("");

    if (!nextFile) {
      setData(null);
      return;
    }

    try {
      setData(JSON.parse(await nextFile.text()));
    } catch {
      setData(null);
      setError("The selected file is not valid JSON.");
    }
  };

  const items = useMemo(() => extractRecords(data), [data]);

  const chapters = useMemo(
    () =>
      [...new Set(items.map((item) => chapterOf(sourceSectionOf(item))))]
        .filter((value) => value && value !== "Unspecified")
        .sort((first, second) =>
          first.localeCompare(second, undefined, { numeric: true }),
        ),
    [items],
  );

  const selected = useMemo(
    () =>
      chapter
        ? items.filter((item) =>
            belongsToChapter(sourceSectionOf(item), chapter),
          )
        : [],
    [chapter, items],
  );

  const includedSections = useMemo(
    () =>
      [...new Set(selected.map(sourceSectionOf))].sort((first, second) =>
        first.localeCompare(second, undefined, { numeric: true }),
      ),
    [selected],
  );

  const grouped = useMemo(() => {
    const normalisedQuery = query.trim().toLowerCase();
    const groups = new Map<string, JsonRecord[]>();

    for (const item of selected) {
      const searchable = JSON.stringify(item).toLowerCase();
      if (normalisedQuery && !searchable.includes(normalisedQuery)) continue;

      const section = sourceSectionOf(item) || chapter || "Other";
      const current = groups.get(section) ?? [];
      current.push(item);
      groups.set(section, current);
    }

    return [...groups.entries()].sort(([first], [second]) =>
      first.localeCompare(second, undefined, { numeric: true }),
    );
  }, [selected, chapter, query]);

  const download = () => {
    if (!chapter) return;

    const output = {
      chapter,
      source_file: cleanSourceFilename(file?.name),
      included_sections: includedSections,
      number_of_requirements: selected.length,
      requirements: selected,
    };

    const blob = new Blob([JSON.stringify(output, null, 2)], {
      type: "application/json",
    });

    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${chapter.replaceAll(".", "_")}_requirements.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Prepare"
        title="Extract chapters"
        description="Choose a broad chapter such as A2. All of its subsections are included, and the extracted requirement text can be reviewed before download."
      />

      <section className="warning-notice" role="alert">
        <strong>Warning:</strong> This tool is for testing purposes only. Cutting the
        specification to just one chapter can remove key related context from other
        chapters.
      </section>

      <section className="panel chapter-extraction-panel">
        <FileUpload
          label="Extracted specification"
          description="Select a requirements or extraction JSON file"
          file={file}
          onChange={load}
        />

        {error && <p className="form-error">{error}</p>}

        {chapters.length > 0 && (
          <>
            <label className="field">
              <span>Chapter to extract</span>
              <select
                value={chapter}
                onChange={(event) => setChapter(event.target.value)}
              >
                <option value="">Select a chapter</option>
                {chapters.map((value) => (
                  <option value={value} key={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>

            {chapter && (
              <>
                <div className="selected-chapter-card">
                  <div>
                    <span>Selected chapter</span>
                    <strong>{chapter}</strong>
                  </div>
                  <p>
                    {selected.length} requirements across {includedSections.length}{" "}
                    sections will be included.
                  </p>
                  <div className="chapter-section-list">
                    {includedSections.map((section) => (
                      <code key={section}>{section}</code>
                    ))}
                  </div>
                </div>

                <section className="chapter-preview" aria-label="Chapter preview">
                  <div className="chapter-preview-header">
                    <div>
                      <h2>Extracted text preview</h2>
                      <p>
                        Review the requirements selected from {chapter} before
                        downloading the file.
                      </p>
                    </div>
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Search this chapter"
                      aria-label="Search selected chapter"
                    />
                  </div>

                  <div className="section-accordion-list">
                    {grouped.map(([section, records], index) => (
                      <details className="section-accordion" key={section} open={index === 0}>
                        <summary>
                          <span>{section}</span>
                          <small>{records.length} requirements</small>
                        </summary>
                        <div className="section-records">
                          {records.map((item, itemIndex) => {
                            const id = requirementIdOf(item) || `Requirement ${itemIndex + 1}`;
                            const text = requirementTextOf(item);

                            return (
                              <article className="requirement-preview" key={`${id}-${itemIndex}`}>
                                <strong>{id}</strong>
                                <p>{text || "No requirement text was provided."}</p>
                              </article>
                            );
                          })}
                        </div>
                      </details>
                    ))}
                  </div>
                </section>

                <button
                  className="button primary"
                  onClick={download}
                  type="button"
                >
                  Download chapter requirements
                </button>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}
