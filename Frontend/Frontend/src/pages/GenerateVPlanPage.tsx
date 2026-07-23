import { useState } from "react";
import { useNavigate } from "react-router-dom";

import FileUpload from "../components/common/FileUpload";
import PageHeader from "../components/common/PageHeader";
import StatusPanel from "../components/common/StatusPanel";
import { useWorkflow } from "../context/WorkflowContext";
import {
  fetchJson,
  postFormData,
} from "../services/api";
import type {
  AgentResponse,
  EdgeCaseDocument,
  VPlanDocument,
  WeakLanguageDocument,
} from "../types/workflow";

export default function GenerateVPlanPage() {
  const navigate = useNavigate();
  const workflow = useWorkflow();

  const [status, setStatus] = useState<
    "idle" | "processing" | "error"
  >("idle");

  const [error, setError] = useState("");
  const run = async () => {
    if (!workflow.requirementsFile) {
      setStatus("error");
      setError(
        "Select a requirements file before generating the vPlan.",
      );
      return;
    }

    setStatus("processing");
    setError("");

    try {
      const formData = new FormData();

      formData.append(
        "requirements_file",
        workflow.requirementsFile,
      );

      const result =
        await postFormData<AgentResponse>(
          "/api/run-agents",
          formData,
        );

      /*
       * Store the complete API response. Coverage relies on
       * requirements_file, vplan_file, edge_case_file and
       * weak_words_file being retained here.
       */
      workflow.setAgentResult(result);

      /*
       * Use the vPlan returned directly by the API.
       * Only download it as a fallback.
       */
      const vplan =
        result.vplan ??
        (await fetchJson<VPlanDocument>(
          result.vplan_download_url,
        ));

      workflow.setVplan(vplan);

      /*
       * The API does not currently return edge-case JSON
       * directly, so load it from its download endpoint.
       */
      const edgeCases =
        result.edge_cases ??
        (await fetchJson<EdgeCaseDocument>(
          result.edge_cases_download_url,
        ));

      workflow.setEdgeCases(edgeCases);

      /*
       * Prefer the weak-language JSON returned directly by
       * the API. Download it only as a fallback.
       */
      let weakLanguage:
        | WeakLanguageDocument
        | null = result.weak_language ?? null;

      if (
        !weakLanguage &&
        result.weak_words_download_url
      ) {
        weakLanguage =
          await fetchJson<WeakLanguageDocument>(
            result.weak_words_download_url,
          );
      }

      workflow.setWeakLanguage(weakLanguage);

      setStatus("idle");

      navigate("/verification/vplan");
    } catch (requestError) {
      setStatus("error");

      setError(
        requestError instanceof Error
          ? requestError.message
          : "Generation failed.",
      );
    }
  };

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Verification"
        title="Generate vPlan"
        description="Upload the refined requirements file used by the current backend workflow. The vPlan, edge cases and weak-language report will be generated together."
      />

      <section className="panel">
        <FileUpload
          label="Requirements file"
          description="Select the refined requirements file"
          file={workflow.requirementsFile}
          onChange={(file) => {
            workflow.setRequirementsFile(file);
            workflow.setRequirementsData(null);

            if (file) {
              file
                .text()
                .then((text) => workflow.setRequirementsData(JSON.parse(text)))
                .catch(() => workflow.setRequirementsData(null));
            }
          }}
          disabled={status === "processing"}
        />

        {status === "processing" && (
          <StatusPanel
            status="processing"
            message="Generating the vPlan, edge cases and weak-language report."
          />
        )}

        {status === "error" && (
          <StatusPanel
            status="error"
            message={error}
          />
        )}

        <div className="button-row">
          <button
            className="button primary"
            disabled={
              !workflow.requirementsFile ||
              status === "processing"
            }
            onClick={run}
            type="button"
          >
            {status === "processing"
              ? "Generating…"
              : "Generate vPlan"}
          </button>

          <button
            className="button secondary"
            onClick={workflow.clearRun}
            disabled={status === "processing"}
            type="button"
          >
            Reset
          </button>
        </div>
      </section>
    </div>
  );
}
