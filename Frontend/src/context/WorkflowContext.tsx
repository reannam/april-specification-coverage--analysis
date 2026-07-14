import { createContext, ReactNode, useContext, useState } from "react";
import type {
  AgentResponse,
  CoverageResponse,
  EdgeCaseDocument,
  VPlanDocument,
  WeakLanguageDocument,
} from "../types/workflow";

type WorkflowState = {
  requirementsFile: File | null;
  setRequirementsFile: (file: File | null) => void;
  requirementsData: unknown;
  setRequirementsData: (value: unknown) => void;
  agentResult: AgentResponse | null;
  setAgentResult: (result: AgentResponse | null) => void;
  vplan: VPlanDocument | null;
  setVplan: (value: VPlanDocument | null) => void;
  edgeCases: EdgeCaseDocument | null;
  setEdgeCases: (value: EdgeCaseDocument | null) => void;
  weakLanguage: WeakLanguageDocument | null;
  setWeakLanguage: (value: WeakLanguageDocument | null) => void;
  coverageResult: CoverageResponse | null;
  setCoverageResult: (value: CoverageResponse | null) => void;
  clearRun: () => void;
};

const Context = createContext<WorkflowState | null>(null);
const AGENT_CACHE_KEY = "spec-workspace-agent-result";
const COVERAGE_CACHE_KEY = "spec-workspace-coverage-result";

const loadCached = <T,>(key: string): T | null => {
  try {
    return JSON.parse(localStorage.getItem(key) ?? "null") as T | null;
  } catch {
    return null;
  }
};

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [cachedAgent] = useState<AgentResponse | null>(() =>
    loadCached<AgentResponse>(AGENT_CACHE_KEY),
  );
  const [cachedCoverage] = useState<CoverageResponse | null>(() =>
    loadCached<CoverageResponse>(COVERAGE_CACHE_KEY),
  );

  const [requirementsFile, setRequirementsFile] = useState<File | null>(null);
  const [requirementsData, setRequirementsData] = useState<unknown>(null);
  const [agentResult, setAgentResultState] = useState<AgentResponse | null>(cachedAgent);
  const [vplan, setVplan] = useState<VPlanDocument | null>(cachedAgent?.vplan ?? null);
  const [edgeCases, setEdgeCases] = useState<EdgeCaseDocument | null>(
    cachedAgent?.edge_cases ?? null,
  );
  const [weakLanguage, setWeakLanguage] = useState<WeakLanguageDocument | null>(
    cachedAgent?.weak_language ?? null,
  );
  const [coverageResult, setCoverageResultState] = useState<CoverageResponse | null>(
    cachedCoverage,
  );

  const setAgentResult = (result: AgentResponse | null) => {
    setAgentResultState(result);

    if (!result) {
      localStorage.removeItem(AGENT_CACHE_KEY);
      return;
    }

    localStorage.setItem(AGENT_CACHE_KEY, JSON.stringify(result));
    if (result.vplan) setVplan(result.vplan);
    if (result.edge_cases) setEdgeCases(result.edge_cases);
    if (result.weak_language) setWeakLanguage(result.weak_language);
  };

  const setCoverageResult = (result: CoverageResponse | null) => {
    setCoverageResultState(result);

    if (result) {
      localStorage.setItem(COVERAGE_CACHE_KEY, JSON.stringify(result));
    } else {
      localStorage.removeItem(COVERAGE_CACHE_KEY);
    }
  };

  const clearRun = () => {
    setRequirementsFile(null);
    setRequirementsData(null);
    setAgentResult(null);
    setVplan(null);
    setEdgeCases(null);
    setWeakLanguage(null);
    setCoverageResult(null);
  };

  return (
    <Context.Provider
      value={{
        requirementsFile,
        setRequirementsFile,
        requirementsData,
        setRequirementsData,
        agentResult,
        setAgentResult,
        vplan,
        setVplan,
        edgeCases,
        setEdgeCases,
        weakLanguage,
        setWeakLanguage,
        coverageResult,
        setCoverageResult,
        clearRun,
      }}
    >
      {children}
    </Context.Provider>
  );
}

export function useWorkflow() {
  const value = useContext(Context);
  if (!value) throw new Error("useWorkflow must be used inside WorkflowProvider");
  return value;
}
