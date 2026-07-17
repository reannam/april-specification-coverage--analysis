import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import HomePage from "./pages/HomePage";
import ExtractPdfPage from "./pages/ExtractPdfPage";
import ExtractRequirementsPage from "./pages/ExtractRequirementsPage";
import ExtractChaptersPage from "./pages/ExtractChaptersPage";
import InconsistenciesPage from "./pages/InconsistenciesPage";
import AmbiguitiesPage from "./pages/AmbiguitiesPage";
import QualityCheckerPage from "./pages/QualityCheckerPage";
import GenerateVPlanPage from "./pages/GenerateVPlanPage";
import VPlanPage from "./pages/VPlanPage";
import EdgeCasesPage from "./pages/EdgeCasesPage";
import WeakLanguagePage from "./pages/WeakLanguagePage";
import CoveragePage from "./pages/CoveragePage";
import CoverageMetricPage from "./pages/CoverageMetricPage";
import MetricsPage from "./pages/MetricsPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="/prepare/pdf" element={<ExtractPdfPage />} />
        <Route path="/prepare/requirements" element={<ExtractRequirementsPage />} />
        <Route path="/prepare/chapters" element={<ExtractChaptersPage />} />
        <Route path="/review/inconsistencies" element={<InconsistenciesPage />} />
        <Route path="/review/ambiguities" element={<AmbiguitiesPage />} />
        <Route path="/review/quality" element={<QualityCheckerPage />} />
        <Route path="/verification/generate" element={<GenerateVPlanPage />} />
        <Route path="/verification/vplan" element={<VPlanPage />} />
        <Route path="/verification/edge-cases" element={<EdgeCasesPage />} />
        <Route path="/verification/weak-language" element={<WeakLanguagePage />} />
        <Route path="/verification/coverage" element={<CoveragePage />} />
        <Route path="/verification/coverage/:metricKey" element={<CoverageMetricPage />} />
        <Route path="/reports/metrics" element={<MetricsPage />} />
        <Route path="/404" element={<NotFoundPage />} />
        <Route path="*" element={<Navigate to="/404" replace />} />
      </Route>
    </Routes>
  );
}
