import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import AdminAuditPage from "./pages/AdminAuditPage";
import AdminUsersPage from "./pages/AdminUsersPage";
import AnalysisHistoryPage from "./pages/AnalysisHistoryPage";
import CaseDetailPage from "./pages/CaseDetailPage";
import CasesPage from "./pages/CasesPage";
import CreateCasePage from "./pages/CreateCasePage";
import DashboardPage from "./pages/DashboardPage";
import DatasetPage from "./pages/DatasetPage";
import LoginPage from "./pages/LoginPage";
import ImageUploadPage from "./pages/ImageUploadPage";
import ModelComparisonPage from "./pages/ModelComparisonPage";
import PreprocessPage from "./pages/PreprocessPage";
import ProfilePage from "./pages/ProfilePage";
import ReportsPage from "./pages/ReportsPage";
import RegisterPage from "./pages/RegisterPage";
import ProtectedRoute from "./routes/ProtectedRoute";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/cases/new" element={<CreateCasePage />} />
          <Route path="/cases/:caseId" element={<CaseDetailPage />} />
          <Route path="/upload" element={<ImageUploadPage />} />
          <Route path="/preprocess" element={<PreprocessPage />} />
          <Route path="/history" element={<AnalysisHistoryPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/models" element={<ModelComparisonPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route element={<ProtectedRoute roles={["data_scientist", "administrator"]} />}>
            <Route path="/dataset" element={<DatasetPage />} />
          </Route>
          <Route element={<ProtectedRoute roles={["administrator"]} />}>
            <Route path="/admin/users" element={<AdminUsersPage />} />
            <Route path="/admin/audit" element={<AdminAuditPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
