import { useMemo, useState } from "react";

type JsonRecord = Record<string, unknown>;

type JsonViewerProps = {
    title: string;
    description?: string;
    data: unknown;
    downloadUrl?: string;
    downloadFilename?: string;
    emptyMessage?: string;
};

const formatLabel = (key: string) => {
    return key
        .replaceAll("_", " ")
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
};

const formatPrimitive = (value: unknown) => {
    if (value === null || value === undefined || value === "") {
        return "Not provided";
    }

    if (typeof value === "boolean") {
        return value ? "Yes" : "No";
    }

    return String(value);
};

const getRecords = (data: unknown): JsonRecord[] => {
    if (Array.isArray(data)) {
        return data.filter(
            (item): item is JsonRecord =>
                typeof item === "object" && item !== null
        );
    }

    if (typeof data !== "object" || data === null) {
        return [];
    }

    const objectData = data as JsonRecord;

    const possibleArrays = [
        "requirements",
        "vplan",
        "tests",
        "items",
        "edge_cases",
        "results",
    ];

    for (const key of possibleArrays) {
        if (Array.isArray(objectData[key])) {
            return (objectData[key] as unknown[]).filter(
                (item): item is JsonRecord =>
                    typeof item === "object" && item !== null
            );
        }
    }

    return [objectData];
};

function JsonViewer({
    title,
    description,
    data,
    downloadUrl,
    downloadFilename = "results.json",
    emptyMessage = "No results are available.",
}: JsonViewerProps) {
    const [viewMode, setViewMode] = useState<"readable" | "raw">("readable");
    const [searchTerm, setSearchTerm] = useState("");

    const records = useMemo(() => getRecords(data), [data]);

    const filteredRecords = useMemo(() => {
        const normalisedSearch = searchTerm.trim().toLowerCase();

        if (!normalisedSearch) {
            return records;
        }

        return records.filter((record) =>
            JSON.stringify(record).toLowerCase().includes(normalisedSearch)
        );
    }, [records, searchTerm]);

    return (
        <section className="jsonViewer">
            <header className="jsonViewerHeader">
                <div>
                    <h3>{title}</h3>
                    {description && <p>{description}</p>}
                </div>

                <div className="jsonViewerActions">
                    <div className="segmentedControl">
                        <button
                            type="button"
                            className={
                                viewMode === "readable" ? "active" : ""
                            }
                            onClick={() => setViewMode("readable")}
                        >
                            Readable view
                        </button>

                        <button
                            type="button"
                            className={viewMode === "raw" ? "active" : ""}
                            onClick={() => setViewMode("raw")}
                        >
                            Raw JSON
                        </button>
                    </div>

                    {downloadUrl && (
                        <a
                            className="button buttonSecondary buttonSmall"
                            href={downloadUrl}
                            download={downloadFilename}
                        >
                            Download JSON
                        </a>
                    )}
                </div>
            </header>

            {records.length === 0 ? (
                <div className="emptyState">
                    <strong>No results</strong>
                    <p>{emptyMessage}</p>
                </div>
            ) : viewMode === "raw" ? (
                <pre className="rawJson">
                    {JSON.stringify(data, null, 2)}
                </pre>
            ) : (
                <>
                    <div className="jsonViewerToolbar">
                        <label>
                            <span className="visuallyHidden">
                                Search results
                            </span>

                            <input
                                type="search"
                                value={searchTerm}
                                placeholder="Search results"
                                onChange={(event) =>
                                    setSearchTerm(event.target.value)
                                }
                            />
                        </label>

                        <span>
                            {filteredRecords.length}{" "}
                            {filteredRecords.length === 1
                                ? "item"
                                : "items"}
                        </span>
                    </div>

                    <div className="recordList">
                        {filteredRecords.map((record, index) => {
                            const primaryId =
                                record.requirement_id ??
                                record.test_id ??
                                record.edge_case_id ??
                                record.id ??
                                `Item ${index + 1}`;

                            return (
                                <article
                                    className="recordCard"
                                    key={`${String(primaryId)}-${index}`}
                                >
                                    <header className="recordCardHeader">
                                        <strong>{String(primaryId)}</strong>

                                        {typeof record.coverage ===
                                            "string" && (
                                            <span className="statusBadge">
                                                {formatLabel(record.coverage)}
                                            </span>
                                        )}
                                    </header>

                                    <dl className="recordFields">
                                        {Object.entries(record).map(
                                            ([key, value]) => (
                                                <div
                                                    className="recordField"
                                                    key={key}
                                                >
                                                    <dt>
                                                        {formatLabel(key)}
                                                    </dt>

                                                    <dd>
                                                        {Array.isArray(
                                                            value
                                                        ) ? (
                                                            <ol>
                                                                {value.map(
                                                                    (
                                                                        item,
                                                                        itemIndex
                                                                    ) => (
                                                                        <li
                                                                            key={
                                                                                itemIndex
                                                                            }
                                                                        >
                                                                            {typeof item ===
                                                                            "object"
                                                                                ? JSON.stringify(
                                                                                      item
                                                                                  )
                                                                                : formatPrimitive(
                                                                                      item
                                                                                  )}
                                                                        </li>
                                                                    )
                                                                )}
                                                            </ol>
                                                        ) : typeof value ===
                                                          "object" ? (
                                                            <pre>
                                                                {JSON.stringify(
                                                                    value,
                                                                    null,
                                                                    2
                                                                )}
                                                            </pre>
                                                        ) : (
                                                            formatPrimitive(
                                                                value
                                                            )
                                                        )}
                                                    </dd>
                                                </div>
                                            )
                                        )}
                                    </dl>
                                </article>
                            );
                        })}
                    </div>
                </>
            )}
        </section>
    );
}

export default JsonViewer;