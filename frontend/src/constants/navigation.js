/** Navigation and pipeline definitions shared by the sidebar and stepper. */

export const ROUTES = {
  dashboard: '/',
  upload: '/upload',
  analysis: '/analysis',
  classical: '/classical',
  quantum: '/quantum',
  comparison: '/comparison',
  recommendation: '/recommendation',
  report: '/report',
}

/**
 * Sidebar sections. `step` drives the numbered progress indicator and tells
 * the layout which flow a page belongs to.
 */
export const NAV_SECTIONS = [
  {
    label: 'Overview',
    items: [
      { key: 'dashboard', label: 'Dashboard', to: ROUTES.dashboard, icon: 'dashboard' },
      { key: 'upload', label: 'Upload Dataset', to: ROUTES.upload, icon: 'upload', step: 1 },
    ],
  },
  {
    label: 'Analysis Pipeline',
    items: [
      { key: 'analysis', label: 'Problem Analysis', to: ROUTES.analysis, icon: 'analysis', step: 2 },
      { key: 'classical', label: 'Classical Analysis', to: ROUTES.classical, icon: 'classical', step: 3 },
      { key: 'quantum', label: 'Quantum Analysis', to: ROUTES.quantum, icon: 'quantum', step: 4 },
      { key: 'comparison', label: 'Comparison', to: ROUTES.comparison, icon: 'comparison', step: 5 },
      { key: 'recommendation', label: 'Recommendation', to: ROUTES.recommendation, icon: 'recommendation', step: 6 },
      { key: 'report', label: 'Detailed Report', to: ROUTES.report, icon: 'report', step: 7 },
    ],
  },
]

/** Flat list of the pipeline steps in execution order. */
export const PIPELINE_STEPS = NAV_SECTIONS[1].items

export const ACCEPTED_FILE_TYPES = ['.csv', '.xlsx', '.json']

export const MAX_UPLOAD_MB = 25

export const PROBLEM_PLACEHOLDER =
  'Predict customer churn using historical customer data.'
