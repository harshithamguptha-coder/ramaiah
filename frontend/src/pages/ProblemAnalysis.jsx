/** Problem Analysis: pipeline stepper, dataset profile and problem classification. */

import { Link } from 'react-router-dom'
import RequireAnalysis from '../components/RequireAnalysis'
import PipelineStepper from '../components/PipelineStepper'
import { Alert, Badge, Button, Card, CardBody, CardFooter, CardHeader, MockBadge, StatTile } from '../components/ui'
import { useAnalysisContext } from '../context/AnalysisContext'
import { formatBytes, formatDateTime, formatNumber } from '../utils/format'

export default function ProblemAnalysis() {
  const { dataset, problem, pipeline, analysisId } = useAnalysisContext()
  const completed = pipeline?.filter((s) => s.status === 'completed').length ?? 0

  return (
    <RequireAnalysis
      title="Dataset & Problem Analysis"
      subtitle="Pipeline stage 2 of 7 — the uploaded file is profiled and the problem statement is classified."
    >
      <Card accent="accent">
        <CardHeader
          title="Analysis pipeline"
          subtitle={`Run ${analysisId}`}
          actions={<Badge tone="success">{completed}/7 stages</Badge>}
        />
        <CardBody>
          <PipelineStepper pipeline={pipeline} current={1} />
        </CardBody>
      </Card>

      <div className="grid grid--sidebar">
        <div className="stack">
          <Card>
            <CardHeader
              title="Dataset profile"
              subtitle={dataset.file_name}
              actions={<Badge tone="info">Structural scan (real)</Badge>}
            />
            <CardBody>
              <div className="grid grid--3">
                <StatTile label="Rows" value={formatNumber(dataset.rows, 'Not parsed')} />
                <StatTile label="Columns" value={formatNumber(dataset.column_count, 'Not parsed')} />
                <StatTile label="File size" value={dataset.file_size_display ?? formatBytes(dataset.file_size_bytes)} />
                <StatTile label="Numerical features" value={formatNumber(dataset.numerical_features)} />
                <StatTile label="Categorical features" value={formatNumber(dataset.categorical_features)} />
                <StatTile
                  label="Missing values"
                  value={formatNumber(dataset.missing_values)}
                  hint={dataset.missing_percent != null ? `${dataset.missing_percent}% of cells` : undefined}
                />
              </div>

              <div className="mt-4">
                <div className="stat__label mb-2">Target column</div>
                {dataset.target_column ? (
                  <div className="chip-row">
                    <Badge tone="brand">{dataset.target_column}</Badge>
                    <span className="small muted">detected by column-name heuristic</span>
                  </div>
                ) : (
                  <div className="small muted">
                    No target column detected — the problem will be treated as unsupervised or
                    unspecified.
                  </div>
                )}
              </div>

              {dataset.column_names?.length > 0 && (
                <div className="mt-4">
                  <div className="stat__label mb-2">Columns ({dataset.column_count})</div>
                  <div className="chip-row">
                    {dataset.column_names.map((name) => (
                      <span
                        className="chip"
                        key={name}
                        style={
                          name === dataset.target_column
                            ? { borderColor: 'var(--brand-400)', color: 'var(--brand-700)', fontWeight: 600 }
                            : undefined
                        }
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </CardBody>
            <CardFooter>
              Profile method: <span className="mono">{dataset.profile_method}</span> · uploaded{' '}
              {formatDateTime(dataset.uploaded_at)}
            </CardFooter>
          </Card>
        </div>


        <div className="stack">
          <Card accent="accent">
            <CardHeader title="Problem classification" actions={<MockBadge label="Mock inference" />} />
            <CardBody>
              <dl className="dl">
                <dt>Task type</dt>
                <dd>{problem.task_type}</dd>
                <dt>Confidence</dt>
                <dd>{Math.round(problem.task_type_confidence * 100)}%</dd>
                <dt>Paradigm</dt>
                <dd>{problem.learning_paradigm}</dd>
                <dt>Modality</dt>
                <dd>{problem.detected_modalities?.join(', ')}</dd>
                <dt>Target</dt>
                <dd className="mono">{problem.target_column || '—'}</dd>
              </dl>

              <div className="mt-4">
                <div className="stat__label mb-2">Detected keywords</div>
                <div className="chip-row">
                  {problem.keywords?.map((keyword) => (
                    <span className="chip" key={keyword}>
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            </CardBody>
            <CardFooter>{problem.note}</CardFooter>
          </Card>

          <Card>
            <CardHeader title="Problem statement" />
            <CardBody>
              <p className="small">{problem.description}</p>
            </CardBody>
          </Card>

          <Alert tone="info" title="What is real and what is mocked">
            Row/column counts, feature types, missing values and the target column are read from
            your file. The task type, confidence and keywords come from a keyword heuristic.
          </Alert>

          <div className="row row--between">
            <Link to="/upload">
              <Button variant="ghost" size="sm">
                Back
              </Button>
            </Link>
            <Link to="/classical">
              <Button variant="primary" iconRight="arrowRight">
                Continue to Classical Analysis
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </RequireAnalysis>
  )
}
