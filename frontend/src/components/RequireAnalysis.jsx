/**
 * Gate for pipeline pages.
 *
 * Every stage after upload depends on an analysis existing. Rather than letting a
 * page render half-empty, this resolves *why* a stage is unavailable and shows a
 * useful state for it.
 *
 * IMPORTANT: pages must never `return null` before calling this component. Doing
 * so bypasses every state below and produces a completely blank page, which is
 * exactly the failure this gate exists to prevent. Pass the stage's own data
 * block as `stage`; the gate returns a helpful state whenever that block is
 * absent, and only then renders `children`.
 */

import { Link } from 'react-router-dom'
import PageHeader from './PageHeader'
import { Alert, Button, EmptyState, LoadingBlock } from './ui'
import { useAnalysisContext } from '../context/AnalysisContext'

export default function RequireAnalysis({
  title,
  subtitle,
  requireComplete = true,
  stage = undefined,
  stageLabel = 'This stage',
  stageError,
  children,
}) {
  const { hasDataset, isComplete, loading, analysisId, error, warnings } =
    useAnalysisContext()

  // A stage that reports itself as failed still renders its own explanation, so
  // it counts as present. Only a *missing* block stops here.
  const stageMissing = stage === null || stage === undefined
  // `skipped` / `failed` stages carry a body the page cannot render (null models),
  // so the gate handles them itself instead of passing them through.
  const stageStatus = stage?.status
  const stageSummary = stage?.summary || stage?.note
  const stageErrors = stage?.errors

  if (loading && analysisId) {
    return (
      <div className="stack">
        <PageHeader title={title} subtitle={subtitle} />
        <LoadingBlock label={`Loading ${stageLabel.toLowerCase()}…`} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="stack">
        <PageHeader title={title} subtitle={subtitle} />
        <Alert tone="danger" title={`Could not run the ${stageLabel.toLowerCase()}`}>
          {error}
        </Alert>
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

  // The run finished but this stage produced no data (for example it failed, or
  // the payload came from an older analysis). Say so rather than rendering
  // nothing - one missing stage must not take the rest of the app down with it.
  if (stageMissing) {
    return (
      <div className="stack">
        <PageHeader title={title} subtitle={subtitle} />
        <Alert tone="warning" title={`${stageLabel} is not available`}>
          {stageError ||
            `This stage did not produce any data for the current analysis${
              warnings?.length ? `: ${warnings[0]}` : '.'
            } Re-run the analysis from the upload page to populate it.`}
        </Alert>
        <StageNav />
      </div>
    )
  }

  // A stage that exists but was skipped or failed (e.g. no target column, so
  // nothing could be trained) must NOT be handed to its page body: that body
  // reads fields like `best_model.name`, which are null here and would crash
  // the render. Explain the skip in place instead - the rest of the pipeline is
  // unaffected and stays reachable.
  if (stageStatus === 'skipped' || stageStatus === 'failed') {
    const detail = stageErrors?.length ? stageErrors.join(' ') : stageSummary
    return (
      <div className="stack">
        <PageHeader title={title} subtitle={subtitle} />
        <Alert
          tone={stageStatus === 'failed' ? 'danger' : 'warning'}
          title={
            stageStatus === 'failed'
              ? `${stageLabel} could not be completed`
              : `${stageLabel} was skipped for this dataset`
          }
        >
          {detail ||
            'This stage had nothing to work on. The remaining pipeline stages were still produced and are available.'}
        </Alert>
        {warnings?.length > 0 && (
          <Alert tone="info" title="Data-quality notes">
            <ul className="small stack stack--sm">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </Alert>
        )}
        <StageNav />
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

/** Keeps the flow navigable when a stage cannot render its body. */
function StageNav() {
  return (
    <div className="row row--tight">
      <Link to="/analysis">
        <Button variant="secondary" size="sm">
          Back to Dataset Analysis
        </Button>
      </Link>
      <Link to="/upload">
        <Button variant="primary" size="sm" icon="arrowRight">
          Re-run the analysis
        </Button>
      </Link>
    </div>
  )
}
