/**
 * Gate for pipeline pages.
 *
 * Every stage after upload depends on an analysis existing. Rather than
 * letting pages render half-empty, this shows an empty state with a direct
 * route back to the upload step.
 */

import { Link } from 'react-router-dom'
import PageHeader from './PageHeader'
import { Button, EmptyState, LoadingBlock } from './ui'
import { useAnalysisContext } from '../context/AnalysisContext'

export default function RequireAnalysis({ title, subtitle, requireComplete = true, children }) {
  const { hasDataset, isComplete, loading, analysisId } = useAnalysisContext()

  if (loading && analysisId) {
    return (
      <div className="stack">
        <PageHeader title={title} subtitle={subtitle} />
        <LoadingBlock label="Loading analysis…" />
      </div>
    )
  }

  if (!hasDataset) {
    return (
      <div className="stack">
        <PageHeader title={title} subtitle={subtitle} />
        <EmptyState
          icon="database"
          title="No dataset uploaded yet"
          action={
            <Link to="/upload">
              <Button variant="primary" icon="upload">
                Go to Upload Dataset
              </Button>
            </Link>
          }
        >
          Upload a dataset and run the analysis before opening this stage. The pipeline always
          starts at the upload step.
        </EmptyState>
      </div>
    )
  }

  if (requireComplete && !isComplete) {
    return (
      <div className="stack">
        <PageHeader title={title} subtitle={subtitle} />
        <EmptyState
          icon="arrowRight"
          title="Analysis has not been started"
          action={
            <Link to="/upload">
              <Button variant="primary" icon="arrowRight">
                Start the analysis
              </Button>
            </Link>
          }
        >
          The dataset is uploaded and profiled. Press <strong>Start Analysis</strong> on the upload
          page to run the remaining pipeline stages.
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="stack">
      <PageHeader title={title} subtitle={subtitle} />
      {children}
    </div>
  )
}
