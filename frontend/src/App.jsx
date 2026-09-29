/**
 * Application root.
 *
 * Routes mirror the Q-Compass pipeline exactly:
 *   Dashboard → Upload → Problem Analysis → Classical → Quantum
 *   → Comparison → Recommendation → Detailed Report
 *
 * A guard in each pipeline page prevents navigating past a missing dataset,
 * so the flow is always followed top to bottom.
 */

import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import { AnalysisProvider } from './context/AnalysisContext'
import ClassicalAnalysis from './pages/ClassicalAnalysis'
import Comparison from './pages/Comparison'
import Dashboard from './pages/Dashboard'
import DetailedReport from './pages/DetailedReport'
import NotFound from './pages/NotFound'
import ProblemAnalysis from './pages/ProblemAnalysis'
import QuantumAnalysis from './pages/QuantumAnalysis'
import Recommendation from './pages/Recommendation'
import UploadDataset from './pages/UploadDataset'

export default function App() {
  return (
    <AnalysisProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="upload" element={<UploadDataset />} />
          <Route path="analysis" element={<ProblemAnalysis />} />
          <Route path="classical" element={<ClassicalAnalysis />} />
          <Route path="quantum" element={<QuantumAnalysis />} />
          <Route path="comparison" element={<Comparison />} />
          <Route path="recommendation" element={<Recommendation />} />
          <Route path="report" element={<DetailedReport />} />
          {/* Legacy/alias paths kept so bookmarks do not 404. */}
          <Route path="problem-analysis" element={<Navigate to="/analysis" replace />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </AnalysisProvider>
  )
}
