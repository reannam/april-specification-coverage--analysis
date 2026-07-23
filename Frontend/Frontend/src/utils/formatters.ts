export type JsonRecord = Record<string, unknown>;

export const humaniseLabel = (value: string) =>
  value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());

export const cleanSourceFilename = (value?: string | null) => {
  if (!value) return null;

  const filename = value.split(/[\\/]/).pop() ?? value;
  return filename.replace(/^[a-f0-9]{32}_/i, "");
};

export const requirementIdOf = (item: JsonRecord) => {
  const value =
    item.requirement_id ??
    item.id ??
    item.requirementId ??
    item.req_id;

  return typeof value === "string" ? value : "";
};

export const requirementTextOf = (item: JsonRecord) => {
  const value =
    item.requirement_text ??
    item.text ??
    item.description ??
    item.requirement ??
    item.statement ??
    item.content;

  return typeof value === "string" ? value : "";
};

export const sourceSectionOf = (item: JsonRecord) => {
  const value =
    item.source_section ??
    item.section ??
    item.section_id ??
    item.chapter;

  return typeof value === "string" ? value.trim() : "";
};

export const sectionFromRequirementId = (requirementId?: string | null) => {
  if (!requirementId) return "Other";

  const match = requirementId
    .toUpperCase()
    .match(/^REQ_([A-Z]+\d+)_(\d+)/);

  if (!match) return "Other";
  return `${match[1]}.${Number(match[2])}`;
};

export const sectionForRecord = (record: JsonRecord) => {
  const explicit = sourceSectionOf(record);
  if (explicit) return explicit;
  return sectionFromRequirementId(requirementIdOf(record));
};

export const extractRecords = (data: unknown): JsonRecord[] => {
  if (Array.isArray(data)) {
    return data.filter(
      (item): item is JsonRecord =>
        Boolean(item) && typeof item === "object" && !Array.isArray(item),
    );
  }

  if (!data || typeof data !== "object") return [];

  const object = data as JsonRecord;
  const keys = [
    "requirements",
    "items",
    "feature_list",
    "extracted_requirements",
    "records",
  ];

  for (const key of keys) {
    if (Array.isArray(object[key])) {
      return extractRecords(object[key]);
    }
  }

  return [];
};

export const buildRequirementTextLookup = (
  requirementsData: unknown,
  vplanTests: Array<{ requirement_id?: string; requirement_text?: string }> = [],
) => {
  const lookup = new Map<string, string>();

  for (const item of extractRecords(requirementsData)) {
    const id = requirementIdOf(item);
    const text = requirementTextOf(item);
    if (id && text) lookup.set(id, text);
  }

  for (const test of vplanTests) {
    if (test.requirement_id && test.requirement_text && !lookup.has(test.requirement_id)) {
      lookup.set(test.requirement_id, test.requirement_text);
    }
  }

  return lookup;
};

export const formatNumber = (value?: number | null) =>
  value === undefined || value === null
    ? "—"
    : new Intl.NumberFormat("en-GB").format(value);

export const formatCost = (value?: string | number | null) => {
  if (value === undefined || value === null || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  return `$${numeric.toFixed(4)}`;
};

export const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
