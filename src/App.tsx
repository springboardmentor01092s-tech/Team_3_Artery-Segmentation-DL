import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import { AdminPreviewGate } from './auth/previewAccess'
import ProtectedRoute from './auth/ProtectedRoute'
import CasesPage from './pages/CasesPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import PatientsPage from './pages/PatientsPage'
import ReportsPage from './pages/ReportsPage'
import ResultsPage from './pages/ResultsPage'
import SettingsPage from './pages/SettingsPage'
import UploadAnalysisPage from './pages/UploadAnalysisPage'
import UsersPage from './pages/UsersPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/patients" element={<PatientsPage />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/upload" element={<UploadAnalysisPage />} />
        <Route path="/analysis" element={<Navigate to="/upload" replace />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/users" element={<AdminPreviewGate><UsersPage /></AdminPreviewGate>} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
