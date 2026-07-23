import { useEffect, useMemo, useState } from "react";
import PageHeader from "../components/common/PageHeader";
import { ChevronIcon, DownloadIcon } from "../components/ui/Icons";
import { useWorkflow } from "../context/WorkflowContext";
import { fetchJson, getDownloadUrl, postFormData } from "../services/api";
import type {
  PrioritiseVPlanResponse,
  VPlanDocument,
  VPlanTest,
} from "../types/workflow";
import { cleanSourceFilename } from "../utils/formatters";

const formatLabel = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());

const MAX_PRIORITY_SELECTIONS = 12;
const SELECTION_SEPARATOR = "::";

type PriorityCategoryGroup = {
  parent: string;
  options: Array<{ label: string; value: string }>;
};

const normaliseVPlan = (document: VPlanDocument): VPlanDocument => ({
  ...document,
  feature_list: (document.feature_list ?? []).map((test) => {
    const isUncovered = test.coverage === "uncovered";

    return {
      ...test,
      category: isUncovered ? "Uncategorised" : test.category || "Uncategorised",
      priority: test.priority ?? 3,
      coverage: test.coverage,
      test_name: isUncovered ? "" : test.test_name,
      test_description: isUncovered ? "" : test.test_description,
      test_steps: isUncovered ? [] : test.test_steps,
      expected_results: isUncovered ? [] : test.expected_results,
    };
  }),
});

const readMetadataString = (
  metadata: Record<string, unknown> | undefined,
  key: string,
) => {
  const value = metadata?.[key];

  return typeof value === "string" && value.trim()
    ? value.trim()
    : null;
};

const getDisplayName = (document: VPlanDocument) => {
  const displayName = readMetadataString(
    document.metadata,
    "display_name",
  );

  if (displayName) {
    return displayName;
  }

  const specificationName = readMetadataString(
    document.metadata,
    "specification_name",
  );

  const section = readMetadataString(
    document.metadata,
    "section",
  );

  if (specificationName && section) {
    return `${specificationName} Section ${section} Verification Plan`;
  }

  if (specificationName) {
    return `${specificationName} Verification Plan`;
  }

  return "Verification Plan";
};

export default function VPlanPage() {
  const workflow = useWorkflow();

  const [document, setDocument] = useState<VPlanDocument | null>(
    workflow.vplan ? normaliseVPlan(workflow.vplan) : null,
  );
  const [query, setQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [scenarioFilter, setScenarioFilter] = useState("all");
  const [coverageFilter, setCoverageFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [expandedTests, setExpandedTests] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");

  const [prioritiseOpen, setPrioritiseOpen] = useState(false);
  const [priorityOneCategories, setPriorityOneCategories] = useState<string[]>([]);
  const [priorityTwoCategories, setPriorityTwoCategories] = useState<string[]>([]);
  const [prioritising, setPrioritising] = useState(false);
  const [prioritiseError, setPrioritiseError] = useState("");

  useEffect(() => {
    if (!document && workflow.agentResult?.vplan_download_url) {
      fetchJson<VPlanDocument>(workflow.agentResult.vplan_download_url)
        .then((loadedDocument) => {
          const normalisedDocument = normaliseVPlan(loadedDocument);
          setDocument(normalisedDocument);
          workflow.setVplan(normalisedDocument);
        })
        .catch((requestError) => setError(String(requestError)));
    }
  }, [document, workflow]);

  const tests = useMemo(() => document?.feature_list ?? [], [document]);

  const displayName = document
    ? getDisplayName(document)
    : "Verification Plan";

  const sourceFilename = cleanSourceFilename(
    readMetadataString(document?.metadata, "requirements_file") ??
      workflow.agentResult?.requirements_file,
  );

  const categories = useMemo(
    () =>
      [...new Set(tests.map((test) => test.category).filter(Boolean))].sort((a, b) =>
        a.localeCompare(b),
      ),
    [tests],
  );

  const priorityCategoryGroups = useMemo<PriorityCategoryGroup[]>(() => {
    const groups = new Map<string, Map<string, string>>();

    tests.forEach((test) => {
      const hasHierarchy =
        test.requirement_category &&
        test.requirement_category !== "Uncategorised" &&
        test.requirement_subcategory;
      const parent = hasHierarchy
        ? test.requirement_category!
        : "Legacy test categories";
      const label = hasHierarchy ? test.requirement_subcategory! : test.category;
      const value = hasHierarchy
        ? `${parent}${SELECTION_SEPARATOR}${label}`
        : label;

      if (!groups.has(parent)) groups.set(parent, new Map());
      groups.get(parent)!.set(value, label);
    });

    return [...groups.entries()]
      .sort(([first], [second]) => first.localeCompare(second))
      .map(([parent, options]) => ({
        parent,
        options: [...options.entries()]
          .map(([value, label]) => ({ label, value }))
          .sort((first, second) => first.label.localeCompare(second.label)),
      }));
  }, [tests]);

  const filteredTests = useMemo(() => {
    const normalisedQuery = query.trim().toLowerCase();

    return tests
      .filter((test) => {
        const matchesSearch =
          !normalisedQuery || JSON.stringify(test).toLowerCase().includes(normalisedQuery);

        return (
          matchesSearch &&
          (priorityFilter === "all" || String(test.priority) === priorityFilter) &&
          (scenarioFilter === "all" || test.scenario_type === scenarioFilter) &&
          (coverageFilter === "all" || test.coverage === coverageFilter) &&
          (categoryFilter === "all" || test.category === categoryFilter)
        );
      })
      .sort((first, second) => {
        if (first.priority !== second.priority) {
          return first.priority - second.priority;
        }

        return first.test_id.localeCompare(second.test_id);
      });
  }, [
    tests,
    query,
    priorityFilter,
    scenarioFilter,
    coverageFilter,
    categoryFilter,
  ]);

  const toggleExpanded = (testId: string) => {
    setExpandedTests((current) => {
      const next = new Set(current);
      if (next.has(testId)) next.delete(testId);
      else next.add(testId);
      return next;
    });
  };

  const toggleCategory = (
    category: string,
    target: "priority-one" | "priority-two",
  ) => {
    if (target === "priority-one") {
      setPriorityTwoCategories((current) => current.filter((value) => value !== category));
      setPriorityOneCategories((current) =>
        current.includes(category)
          ? current.filter((value) => value !== category)
          : [...current, category],
      );
      return;
    }

    setPriorityOneCategories((current) => current.filter((value) => value !== category));
    setPriorityTwoCategories((current) =>
      current.includes(category)
        ? current.filter((value) => value !== category)
        : [...current, category],
    );
  };

  const selectedCategoryCount =
    priorityOneCategories.length + priorityTwoCategories.length;

  const applyPriorities = async () => {
    const vplanFile =
      workflow.agentResult?.vplan_file ??
      workflow.agentResult?.vplan_download_url;

    if (!vplanFile) {
      setPrioritiseError(
        "The backend vPlan path is unavailable. Generate the vPlan again before prioritising it.",
      );
      return;
    }

    if (
      selectedCategoryCount < 2 ||
      selectedCategoryCount > MAX_PRIORITY_SELECTIONS
    ) {
      setPrioritiseError(
        `Select between 2 and ${MAX_PRIORITY_SELECTIONS} categories or subcategories.`,
      );
      return;
    }

    if (priorityOneCategories.length === 0) {
      setPrioritiseError("Select at least one Priority 1 category.");
      return;
    }

    setPrioritising(true);
    setPrioritiseError("");

    try {
      const formData = new FormData();
      formData.append("vplan_file", vplanFile);
      formData.append("priority_1_categories", JSON.stringify(priorityOneCategories));
      formData.append("priority_2_categories", JSON.stringify(priorityTwoCategories));

      const response = await postFormData<PrioritiseVPlanResponse>(
        "/api/prioritise-vplan",
        formData,
      );

      const updatedDocument = normaliseVPlan(response.vplan);
      setDocument(updatedDocument);
      workflow.setVplan(updatedDocument);

      workflow.setAgentResult({
        ...workflow.agentResult!,
        vplan_file: response.vplan_file,
        vplan_filename: response.vplan_filename,
        vplan_download_url: response.vplan_download_url,
      });

      setPriorityFilter("all");
      setPrioritiseOpen(false);
      setPriorityOneCategories([]);
      setPriorityTwoCategories([]);
    } catch (requestError) {
      setPrioritiseError(
        requestError instanceof Error ? requestError.message : "The vPlan could not be prioritised.",
      );
    } finally {
      setPrioritising(false);
    }
  };

  if (!document) {
    return (
      <div className="empty-state">
        <strong>No vPlan loaded</strong>
        <p>{error || "Generate a vPlan first, or return to the generation page."}</p>
      </div>
    );
  }

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Generated output"
        title="vPlan"
        description={`${displayName} · ${tests.length} tests · ${categories.length} categories`}
        actions={
          <div className="page-actions">
            <button className="button secondary" onClick={() => setPrioritiseOpen(true)}>
              Prioritise
            </button>

            {workflow.agentResult?.vplan_download_url && (
              <a
                className="button primary"
                href={getDownloadUrl(workflow.agentResult.vplan_download_url)}
                download={workflow.agentResult.vplan_filename}
              >
                <DownloadIcon />
                Download vPlan
              </a>
            )}
          </div>
        }
      />

      <div className="toolbar">
        <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
          <option value="all">All categories</option>
          {categories.map((category) => (
            <option value={category} key={category}>
              {category}
            </option>
          ))}
        </select>

        <select value={scenarioFilter} onChange={(event) => setScenarioFilter(event.target.value)}>
          <option value="all">All scenarios</option>
          <option value="nominal">Nominal</option>
          <option value="illegal">Illegal</option>
          <option value="corner">Corner</option>
        </select>

        <select value={coverageFilter} onChange={(event) => setCoverageFilter(event.target.value)}>
          <option value="all">All coverage</option>
          <option value="covered">Covered</option>
          <option value="partially_covered">Partially covered</option>
          <option value="uncovered">Uncovered</option>
        </select>

        <select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}>
          <option value="all">All priorities</option>
          <option value="1">Priority 1</option>
          <option value="2">Priority 2</option>
          <option value="3">Priority 3</option>
        </select>

        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search the entire vPlan"
          aria-label="Search the entire vPlan"
        />

        <button onClick={() => setExpandedTests(new Set(filteredTests.map((test) => test.test_id)))}>
          Expand all
        </button>
        <button onClick={() => setExpandedTests(new Set())}>Collapse all</button>
      </div>

      <section className="vplan-box">
        <header>
          <h2>{displayName}</h2>
          <p>
            Showing {filteredTests.length} of {tests.length} tests
            {sourceFilename ? ` · Source: ${sourceFilename}` : ""}
          </p>
        </header>

        {filteredTests.length === 0 ? (
          <div className="empty-state">
            <strong>No matching tests</strong>
            <p>Change the search term or remove one of the filters.</p>
          </div>
        ) : (
          filteredTests.map((test) => (
            <TestRow
              key={test.test_id}
              test={test}
              expanded={expandedTests.has(test.test_id)}
              toggle={() => toggleExpanded(test.test_id)}
            />
          ))
        )}
      </section>

      {prioritiseOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => !prioritising && setPrioritiseOpen(false)}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="prioritise-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="modal-header">
              <div>
                <p className="eyebrow">vPlan ordering</p>
                <h2 id="prioritise-title">Prioritise vPlan</h2>
                <p>
                  Select 2–{MAX_PRIORITY_SELECTIONS} subcategories across the major
                  categories. Unselected areas will receive Priority 3.
                </p>
              </div>
              <button
                className="modal-close"
                type="button"
                disabled={prioritising}
                onClick={() => setPrioritiseOpen(false)}
                aria-label="Close prioritisation dialog"
              >
                ×
              </button>
            </header>

            <div className="priority-selection">
              <CategorySelection
                title="Priority 1 — highest"
                description="Tests in these categories will be surfaced first."
                groups={priorityCategoryGroups}
                selected={priorityOneCategories}
                otherSelected={priorityTwoCategories}
                onToggle={(category) => toggleCategory(category, "priority-one")}
              />

              <CategorySelection
                title="Priority 2"
                description="Tests in these categories will follow Priority 1."
                groups={priorityCategoryGroups}
                selected={priorityTwoCategories}
                otherSelected={priorityOneCategories}
                onToggle={(category) => toggleCategory(category, "priority-two")}
              />

              <div className="priority-three-note">
                <strong>Priority 3</strong>
                <p>All remaining categories will automatically receive the lowest priority.</p>
              </div>
            </div>

            <div className="selection-count">
              {selectedCategoryCount} of 2–{MAX_PRIORITY_SELECTIONS} categories or
              subcategories selected
            </div>

            {prioritiseError && <p className="modal-error">{prioritiseError}</p>}

            <footer className="modal-footer">
              <button
                className="button secondary"
                type="button"
                disabled={prioritising}
                onClick={() => setPrioritiseOpen(false)}
              >
                Cancel
              </button>
              <button
                className="button primary"
                type="button"
                disabled={
                  prioritising ||
                  selectedCategoryCount < 2 ||
                  selectedCategoryCount > MAX_PRIORITY_SELECTIONS ||
                  priorityOneCategories.length === 0
                }
                onClick={applyPriorities}
              >
                {prioritising ? "Applying priorities…" : "Apply priorities"}
              </button>
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}

function CategorySelection({
  title,
  description,
  groups,
  selected,
  otherSelected,
  onToggle,
}: {
  title: string;
  description: string;
  groups: PriorityCategoryGroup[];
  selected: string[];
  otherSelected: string[];
  onToggle: (category: string) => void;
}) {
  return (
    <section className="category-selection">
      <header>
        <h3>{title}</h3>
        <p>{description}</p>
      </header>

      <div className="category-groups">
        {groups.map((group) => (
          <section className="category-group" key={group.parent}>
            <h4>{group.parent}</h4>
            <div className="category-options">
              {group.options.map((option) => {
                const isSelected = selected.includes(option.value);
                const isSelectedElsewhere = otherSelected.includes(option.value);

                return (
                  <button
                    className={`category-option ${isSelected ? "selected" : ""}`}
                    type="button"
                    aria-pressed={isSelected}
                    key={option.value}
                    onClick={() => onToggle(option.value)}
                    title={
                      isSelectedElsewhere
                        ? `${option.label} is currently assigned to the other priority group`
                        : undefined
                    }
                  >
                    <span>{option.label}</span>
                    {isSelected && <strong>✓</strong>}
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}

function TestRow({
  test,
  expanded,
  toggle,
}: {
  test: VPlanTest;
  expanded: boolean;
  toggle: () => void;
}) {
  const displayName =
    test.coverage === "uncovered"
      ? "Uncovered requirement"
      : test.test_name || test.test_id;

  return (
    <article className={`test-row ${expanded ? "expanded" : ""}`}>
      <button className="test-summary" onClick={toggle} type="button">
        <span className="chevron">
          <ChevronIcon open={expanded} />
        </span>

        <span>
          <strong>{displayName}</strong>
          <small>
            {test.test_name && <>{test.test_id}{" · "}</>}
            <b>{formatLabel(test.scenario_type)}</b>
            {" · "}
            {test.category}
            {" · "}
            Priority {test.priority}
            {" · "}
            {formatLabel(test.coverage)}
          </small>
        </span>

        <code>{test.requirement_id}</code>
      </button>

      {expanded && (
        <dl className="test-details">
          <Field label="Related requirement" value={test.requirement_id} />
          <Field
            label="Test name"
            value={
              test.coverage === "uncovered"
                ? "Not generated — requirement is uncovered"
                : test.test_name || test.test_id
            }
          />
          <Field
            label="Requirement category"
            value={test.requirement_category || "Uncategorised"}
          />
          <Field
            label="Requirement subcategory"
            value={test.requirement_subcategory || "Uncategorised"}
          />
          <Field
            label="Supporting requirements"
            value={
              test.supporting_requirement_ids?.length
                ? test.supporting_requirement_ids.join(", ")
                : "None"
            }
          />
          <Field label="Category" value={test.category} />
          <Field label="Priority" value={`Priority ${test.priority}`} />
          <Field label="Scenario type" value={formatLabel(test.scenario_type)} />

          {test.requirement_text && (
            <Field label="Requirement text" value={test.requirement_text} wide />
          )}

          <Field label="Test description" value={test.test_description} wide />
          <Field
            label="Test constraints"
            value={test.test_constraints || "None specified"}
            wide
          />
          <List label="Test steps" items={test.test_steps} />
          <List label="Expected results" items={test.expected_results} />
        </dl>
      )}
    </article>
  );
}

function Field({
  label,
  value,
  wide = false,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "wide" : ""}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function List({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="wide">
      <dt>{label}</dt>
      <dd>
        {items.length > 0 ? (
          <ol>
            {items.map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ol>
        ) : (
          "None specified"
        )}
      </dd>
    </div>
  );
}
