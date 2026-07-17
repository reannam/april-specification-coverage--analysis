import React, { useMemo, useState } from "react";

type JsonObject = Record<string, unknown>;

type Section = {
  id: string;
  title?: string;
  parent?: string;
};

type ChapterOption = {
  id: string;
  title: string;
  sectionCount: number;
};

type ExtractionResult = JsonObject & {
  selected_chapter: {
    id: string;
    title: string;
    section_ids: string[];
    page_numbers: number[];
  };
  extraction_summary: {
    sections: number;
    requirements: number;
    figures: number;
    tables: number;
    notes: number;
    acronyms: number;
    cross_references: number;
    semantic_chunks: number;
    pages: number;
  };
};

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normaliseWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function uniqueBy<T>(items: T[], keyFn: (item: T) => string): T[] {
  const seen = new Set<string>();
  const output: T[] = [];

  for (const item of items) {
    const key = keyFn(item);
    if (!seen.has(key)) {
      seen.add(key);
      output.push(item);
    }
  }

  return output;
}

function asArray<T = JsonObject>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function getSectionId(value: JsonObject): string | undefined {
  const section = value.section ?? value.source_section ?? value.section_id;
  return section === undefined || section === null ? undefined : String(section);
}

function belongsToChapter(
  sectionId: string | undefined,
  chapterId: string,
): boolean {
  if (!sectionId) return false;
  return sectionId === chapterId || sectionId.startsWith(`${chapterId}.`);
}

function pageHasChapterMarker(page: JsonObject, chapterId: string): boolean {
  const text = String(page.text ?? "");
  const chapterPattern = new RegExp(
    `\\bChapter\\s+${escapeRegex(chapterId)}\\b`,
  );
  return chapterPattern.test(text);
}

function textContainsWholeToken(text: string, token: string): boolean {
  if (!token) return false;
  const pattern = new RegExp(`\\b${escapeRegex(token)}\\b`);
  return pattern.test(text);
}

function inferChapterTitle(
  documentJson: JsonObject,
  chapterId: string,
): string {
  const pages = asArray<JsonObject>(documentJson.pages);
  const chapterPage = pages.find((page) =>
    pageHasChapterMarker(page, chapterId),
  );
  const text = String(chapterPage?.text ?? "");

  const splitFormat = text.match(
    new RegExp(`Chapter\\s+${escapeRegex(chapterId)}\\s*\\n([^\\n]+)`),
  );
  if (splitFormat?.[1]) return normaliseWhitespace(splitFormat[1]);

  const inlineFormat = text.match(
    new RegExp(`Chapter\\s+${escapeRegex(chapterId)}\\.\\s*([^\\n]+)`),
  );
  if (inlineFormat?.[1]) return normaliseWhitespace(inlineFormat[1]);

  return chapterId;
}

function normaliseRequirementText(text: string): string {
  return normaliseWhitespace(text)
    .toLowerCase()
    .replace(/\bfigure\s+[a-z]\d+\.\d+\b/g, "")
    .replace(/\btable\s+[a-z]\d+\.\d+\b/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function hasNormativeLanguage(text: string): boolean {
  return /\b(shall|must|required|requires|requirement|must not|shall not|not permitted|is permitted|are permitted|can only|cannot|always|never|supports|does not support)\b/i.test(
    text,
  );
}

function isFigureOrTableDerivedRequirement(requirement: JsonObject): boolean {
  const text = String(requirement.text ?? "");
  const sourceKind = String(
    requirement.source_kind ?? requirement.source_type ?? "",
  ).toLowerCase();

  return (
    sourceKind.includes("figure") ||
    sourceKind.includes("ocr") ||
    sourceKind.includes("caption") ||
    /\b(?:in\s+)?figure\s+[a-z]\d+\.\d+\b/i.test(text) ||
    /\b(?:in\s+)?table\s+[a-z]\d+\.\d+\b/i.test(text)
  );
}

function isLikelyExplanatoryRequirement(requirement: JsonObject): boolean {
  const text = String(requirement.text ?? "");

  return (
    /\bfor example\b/i.test(text) ||
    /\bhappen(?:s|ed)? to\b/i.test(text) ||
    /\bshows?\b/i.test(text) ||
    /\billustrates?\b/i.test(text) ||
    /\bdepicts?\b/i.test(text) ||
    /\bpoint to signals\b/i.test(text)
  );
}

function getRequirementEvidence(requirement: JsonObject): JsonObject[] {
  const existingEvidence = asArray<JsonObject>(requirement.evidence);
  const evidence: JsonObject[] = [...existingEvidence];

  if (isFigureOrTableDerivedRequirement(requirement)) {
    evidence.push({
      source_kind: "figure_or_table_context",
      original_id: requirement.id,
      source_section: requirement.source_section,
      text: requirement.text,
    });
  }

  return evidence;
}

function mergeRequirementEvidence(
  primary: JsonObject,
  duplicate: JsonObject,
): JsonObject {
  const primaryEvidence = asArray<JsonObject>(primary.evidence);
  const duplicateEvidence = getRequirementEvidence(duplicate);

  return {
    ...primary,
    evidence: uniqueBy([...primaryEvidence, ...duplicateEvidence], (item) =>
      JSON.stringify(item),
    ),
  };
}

function assignStableRequirementIds(requirements: JsonObject[]): JsonObject[] {
  const counters = new Map<string, number>();

  return requirements.map((requirement) => {
    const sourceSection = String(requirement.source_section ?? "REQ");
    const sectionKey = sourceSection
      .replace(/[^A-Za-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
    const nextCount = (counters.get(sectionKey) ?? 0) + 1;
    counters.set(sectionKey, nextCount);

    return {
      ...requirement,
      original_id: requirement.original_id ?? requirement.id,
      id: `REQ_${sectionKey}_${String(nextCount).padStart(3, "0")}`,
    };
  });
}

function deduplicateRequirements(requirements: JsonObject[]): {
  requirements: JsonObject[];
  report: JsonObject;
} {
  const duplicateIdCounts = requirements.reduce<Record<string, number>>(
    (counts, requirement) => {
      const id = String(requirement.id ?? "");
      if (!id) return counts;
      counts[id] = (counts[id] ?? 0) + 1;
      return counts;
    },
    {},
  );

  const duplicateIdCollisions = Object.entries(duplicateIdCounts).filter(
    ([, count]) => count > 1,
  ).length;

  const discardedFigureOrTableRequirements: JsonObject[] = [];
  const nonExplanatoryRequirements = requirements.filter((requirement) => {
    const shouldDiscard =
      isFigureOrTableDerivedRequirement(requirement) &&
      isLikelyExplanatoryRequirement(requirement) &&
      !hasNormativeLanguage(String(requirement.text ?? ""));

    if (shouldDiscard) discardedFigureOrTableRequirements.push(requirement);
    return !shouldDiscard;
  });

  const byText = new Map<string, JsonObject>();
  let exactDuplicatesRemoved = 0;

  for (const requirement of nonExplanatoryRequirements) {
    const sourceSection = String(requirement.source_section ?? "");
    const normalisedText = normaliseRequirementText(
      String(requirement.text ?? ""),
    );
    const key = `${sourceSection}|${normalisedText}`;
    const existing = byText.get(key);

    if (existing) {
      exactDuplicatesRemoved += 1;
      byText.set(key, mergeRequirementEvidence(existing, requirement));
      continue;
    }

    byText.set(key, {
      ...requirement,
      evidence: asArray<JsonObject>(requirement.evidence),
    });
  }

  const deduplicated = [...byText.values()];
  const reassigned = assignStableRequirementIds(deduplicated);

  return {
    requirements: reassigned,
    report: {
      input_requirements: requirements.length,
      output_requirements: reassigned.length,
      exact_duplicates_removed: exactDuplicatesRemoved,
      discarded_figure_or_table_explanations:
        discardedFigureOrTableRequirements.length,
      duplicate_id_collisions_found: duplicateIdCollisions,
      final_ids_reassigned: true,
    },
  };
}

export function getChapterOptions(documentJson: JsonObject): ChapterOption[] {
  const sections = asArray<Section>(documentJson.sections).filter(
    (section) => section.id,
  );
  const grouped = new Map<string, Section[]>();

  for (const section of sections) {
    const chapterId = section.parent || section.id.split(".")[0];
    if (!chapterId) continue;
    grouped.set(chapterId, [...(grouped.get(chapterId) ?? []), section]);
  }

  return [...grouped.entries()]
    .map(([id, chapterSections]) => ({
      id,
      title: inferChapterTitle(documentJson, id),
      sectionCount: chapterSections.length,
    }))
    .sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
}

export function extractChapterJson(
  documentJson: JsonObject,
  chapterId: string,
): ExtractionResult {
  const sections = asArray<Section>(documentJson.sections).filter(
    (section) =>
      section.parent === chapterId || belongsToChapter(section.id, chapterId),
  );
  const sectionIds = new Set(sections.map((section) => section.id));

  const pages = asArray<JsonObject>(documentJson.pages).filter((page) => {
    const headings = asArray<JsonObject>(page.headings);
    const hasMatchingHeading = headings.some((heading) =>
      sectionIds.has(String(heading.section_id ?? "")),
    );
    return pageHasChapterMarker(page, chapterId) || hasMatchingHeading;
  });

  const pageNumbers = new Set(
    pages
      .map((page) => Number(page.page_number))
      .filter(Number.isFinite),
  );
  const selectedPageText = pages
    .map((page) => String(page.text ?? ""))
    .join("\n");
  const selectedPageTextNormalised = normaliseWhitespace(selectedPageText);

  const rawRequirements = asArray<JsonObject>(documentJson.requirements).filter(
    (requirement) => sectionIds.has(String(requirement.source_section ?? "")),
  );
  const { requirements, report: deduplicationReport } =
    deduplicateRequirements(rawRequirements);

  const figures = asArray<JsonObject>(documentJson.figures).filter((figure) => {
    const figureSection = String(figure.section ?? "");
    const caption = String(figure.caption ?? "");
    const pageNumber = figure.page;

    return (
      sectionIds.has(figureSection) ||
      (pageNumbers.has(Number(pageNumber)) &&
        new RegExp(`\\bFigure\\s+${escapeRegex(chapterId)}\\.`).test(caption))
    );
  });

  const tables = asArray<JsonObject>(documentJson.tables).filter((table) => {
    const tableSection = getSectionId(table);
    if (belongsToChapter(tableSection, chapterId)) return true;
    return pageNumbers.has(Number(table.page));
  });

  const semanticChunks = asArray<JsonObject>(
    documentJson.semantic_chunks,
  ).filter((chunk) => belongsToChapter(String(chunk.section ?? ""), chapterId));

  const notes = asArray<JsonObject>(documentJson.notes).filter((note) => {
    const noteSection = getSectionId(note);
    if (belongsToChapter(noteSection, chapterId)) return true;

    const noteText = normaliseWhitespace(String(note.text ?? ""));
    return noteText.length > 0 && selectedPageTextNormalised.includes(noteText);
  });

  const acronyms = asArray<string>(documentJson.acronyms).filter((acronym) =>
    textContainsWholeToken(selectedPageText, String(acronym)),
  );

  const crossReferences = asArray<string>(documentJson.cross_references).filter(
    (reference) => {
      const value = String(reference);
      return new RegExp(
        `\\b(?:Figure|Table)\\s+${escapeRegex(chapterId)}\\.`,
      ).test(value);
    },
  );

  const uniqueFigures = uniqueBy(
    figures,
    (figure) =>
      `${figure.caption ?? ""}|${figure.page ?? ""}|${figure.file ?? ""}`,
  );
  const uniqueTables = uniqueBy(
    tables,
    (table) => `${table.csv_file ?? ""}|${table.page ?? ""}`,
  );
  const uniqueAcronyms = uniqueBy(acronyms, String);

  const chapterTitle = inferChapterTitle(documentJson, chapterId);
  const sortedPageNumbers = [...pageNumbers].sort((a, b) => a - b);

  return {
    document_name: documentJson.document_name,
    metadata: documentJson.metadata,
    total_pages: documentJson.total_pages,
    selected_chapter: {
      id: chapterId,
      title: chapterTitle,
      section_ids: [...sectionIds],
      page_numbers: sortedPageNumbers,
    },
    sections,
    requirements,
    deduplication_report: deduplicationReport,
    figures: uniqueFigures,
    tables: uniqueTables,
    notes,
    acronyms: uniqueAcronyms,
    cross_references: crossReferences,
    semantic_chunks: semanticChunks,
    pages,
    extraction_summary: {
      sections: sections.length,
      requirements: requirements.length,
      figures: uniqueFigures.length,
      tables: uniqueTables.length,
      notes: notes.length,
      acronyms: uniqueAcronyms.length,
      cross_references: crossReferences.length,
      semantic_chunks: semanticChunks.length,
      pages: pages.length,
    },
  };
}

export default function ChapterExtractionFlow() {
  const [documentJson, setDocumentJson] = useState<JsonObject | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const [selectedChapterId, setSelectedChapterId] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [copyMessage, setCopyMessage] = useState<string>("");

  const chapters = useMemo(
    () => (documentJson ? getChapterOptions(documentJson) : []),
    [documentJson],
  );

  const extractedJson = useMemo(() => {
    if (!documentJson || !selectedChapterId) return null;
    return extractChapterJson(documentJson, selectedChapterId);
  }, [documentJson, selectedChapterId]);

  async function handleFileUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const parsed = JSON.parse(text);

      if (!Array.isArray(parsed.sections)) {
        throw new Error("The uploaded JSON does not contain a sections array.");
      }

      const options = getChapterOptions(parsed);
      setDocumentJson(parsed);
      setFileName(file.name);
      setSelectedChapterId(options[0]?.id ?? "");
      setError("");
      setCopyMessage("");
    } catch (uploadError) {
      setDocumentJson(null);
      setFileName("");
      setSelectedChapterId("");
      setCopyMessage("");
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Could not parse the uploaded JSON file.",
      );
    }
  }

  function downloadExtractedJson() {
    if (!extractedJson || !selectedChapterId) return;

    const blob = new Blob([JSON.stringify(extractedJson, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedChapterId.toLowerCase()}_extracted_chapter.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copyExtractedJson() {
    if (!extractedJson) return;
    await navigator.clipboard.writeText(JSON.stringify(extractedJson, null, 2));
    setCopyMessage("Copied JSON to clipboard.");
  }

  return (
    <div className="chapterExtractor">
      <section className="chapterExtractorCard">
        <div className="chapterExtractorHeader">
          <div>
            <p className="eyebrow">Deterministic extraction</p>
            <h2>Chapter JSON extractor</h2>
            <p>
              Upload an extracted specification JSON, choose a chapter, then
              export only the matching sections, requirements, figures, tables,
              pages, chunks, acronyms and cross-references.
            </p>
          </div>
        </div>

        <div className="chapterExtractorControls">
          <label className="chapterExtractorField">
            <span>Specification JSON</span>
            <input
              type="file"
              accept="application/json,.json"
              onChange={handleFileUpload}
            />
          </label>

          <label className="chapterExtractorField">
            <span>Chapter</span>
            <select
              value={selectedChapterId}
              onChange={(event) => setSelectedChapterId(event.target.value)}
              disabled={!chapters.length}
            >
              {chapters.length === 0 && (
                <option value="">Upload a JSON file first</option>
              )}
              {chapters.map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  {chapter.id} — {chapter.title} ({chapter.sectionCount}{" "}
                  sections)
                </option>
              ))}
            </select>
          </label>
        </div>

        {fileName && <p className="chapterExtractorMeta">Loaded: {fileName}</p>}

        {error && (
          <div className="alert error">
            <strong>Upload failed</strong>
            <p>{error}</p>
          </div>
        )}
      </section>

      {extractedJson && (
        <section className="chapterExtractorCard">
          <div className="chapterExtractorResultHeader">
            <div>
              <h2>
                {extractedJson.selected_chapter.id} —{" "}
                {extractedJson.selected_chapter.title}
              </h2>
              <p>
                Pages {extractedJson.selected_chapter.page_numbers[0] ?? "?"}–
                {extractedJson.selected_chapter.page_numbers.at(-1) ?? "?"} ·{" "}
                {extractedJson.extraction_summary.requirements} requirements
              </p>
            </div>

            <div className="chapterExtractorActions">
              <button
                type="button"
                className="ghostButton"
                onClick={copyExtractedJson}
              >
                Copy JSON
              </button>
              <button
                type="button"
                className="primaryButton"
                onClick={downloadExtractedJson}
              >
                Download JSON
              </button>
            </div>
          </div>

          {copyMessage && <p className="chapterExtractorMeta">{copyMessage}</p>}

          <div className="chapterSummaryGrid">
            {Object.entries(extractedJson.extraction_summary).map(
              ([label, count]) => (
                <div key={label} className="chapterSummaryCard">
                  <span>{label.replaceAll("_", " ")}</span>
                  <strong>{count}</strong>
                </div>
              ),
            )}
          </div>

          <pre className="chapterJsonPreview">
            {JSON.stringify(extractedJson, null, 2)}
          </pre>
        </section>
      )}
    </div>
  );
}
