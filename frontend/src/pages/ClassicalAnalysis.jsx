/** Classical Analysis: candidate models, baseline, complexity and resources. */

import { Link } from 'react-router-dom'
import RequireAnalysis from '../components/RequireAnalysis'
import PipelineStepper from '../components/PipelineStepper'
import { Alert, Badge, Button, Card, CardBody, CardFooter, CardHeader, SourceBadge, StatTile } from '../components/ui'
import { ColumnChart } from '../components/charts'
import { useAnalysisContext } from '../context/AnalysisContext'
import { formatSeconds } from '../utils/format'

export default function ClassicalAnalysis() {
  const { classical, pipeline } = useAnalysisContext()

  return (
    <RequireAnalysis
      title="Classical AI Analysis"
      subtitle="Pipeline stage 3 of 7 — classical algorithm candidates, baseline and resource estimates."
      stage={classical}
      stageLabel="Classical AI analysis"
    >
      {classical ? <ClassicalStage classical={classical} pipeline={pipeline} /> : null}
    </RequireAnalysis>
  )
}

/**
 * The stage body. Split out so the measured data is only touched once it is
 * known to exist — the page must never return `null` on missing data, or the
 * route renders as a blank page instead of explaining itself.
 */
function ClassicalStage({ classical, pipeline }) {
  const { candidates, best_model: best, baseline_model: baseline, estimated_complexity: complexity } = classical
  const resources = classical.resource_requirements
  const size = classical.dataset_size
  // Regression has no accuracy/F1, so the table headers follow the measured task.
  const isRegression = classical.task === 'regression'

  return (
    <>
      <Card accent="classical">
        <CardHeader title="Analysis pipeline" actions={<SourceBadge block={classical} label="Models trained" />} />
        <CardBody>
          <PipelineStepper pipeline={pipeline} current={2} />
        </CardBody>
      </Card>

      <div className="grid grid--4">
        <StatTile
          label="Best model"
          value={best.name}
          hint={best.summary || `${((best.accuracy ?? 0) * 100).toFixed(1)}% accuracy`}
        />
        <StatTile
          label="Baseline"
          value={baseline?.name || '—'}
          hint={baseline?.summary || 'Trivial reference to beat'}
        />
        <StatTile
          label="Primary metric"
          value={classical.primary_metric || '—'}
          hint={
            classical.status === 'completed'
              ? `${candidates.length} models trained`
              : classical.status
          }
        />
        <StatTile label="Dataset size" value={`${size.size_mb} MB`} hint={size.label} />
        <StatTile
          label="Expected runtime"
          value={resources.expected_runtime}
          hint={`${resources.cpu_cores} CPU cores · ${resources.memory_gb} GB RAM`}
        />
      </div>

      <div className="grid grid--sidebar">
        <div className="stack">
          <Card>
            <CardHeader
              title="Algorithm candidates"
              subtitle={`${candidates.length} models for a ${size.rows.toLocaleString()} × ${size.columns} dataset`}
              actions={<SourceBadge block={classical} label="Measured" />}
            />
            <CardBody tight>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Algorithm</th>
                      <th>Family</th>
                      <th className="num">{isRegression ? 'R2' : 'Accuracy'}</th>
                      <th className="num">{isRegression ? 'RMSE' : 'F1'}</th>
                      <th className="num">Training time</th>
                      <th>Complexity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((model) => (
                      <tr key={model.name}>
                        <td>
                          <div style={{ fontWeight: 650 }}>{model.name}</div>
                          {model.name === best.name && <Badge tone="success">Best</Badge>}
                          {model.name === baseline?.name && <Badge tone="neutral">Baseline</Badge>}
                        </td>
                        <td className="muted">{model.family}</td>
                        <td className="num">
                          {isRegression ? model.r2 : `${((model.accuracy ?? 0) * 100).toFixed(1)}%`}
                        </td>
                        <td className="num">
                          {isRegression ? model.rmse : `${((model.f1_score ?? 0) * 100).toFixed(1)}%`}
                        </td>
                        <td className="num">{formatSeconds(model.training_time_sec)}</td>
                        <td className="mono small">{model.complexity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
            <CardFooter>{classical.note}</CardFooter>
          </Card>

          <Card>
            <CardHeader title={`Measured ${isRegression ? 'R2' : 'accuracy'} by candidate`} />
            <CardBody>
              <ColumnChart
                suffix={isRegression ? '' : '%'}
                data={candidates.map((m) => ({
                  label: m.name.length > 16 ? `${m.name.slice(0, 15)}…` : m.name,
                  value: isRegression ? (m.r2 ?? 0) * 100 : (m.accuracy ?? 0) * 100,
                  tone: m.name === best.name ? 'success' : 'classical',
                }))}
              />
            </CardBody>
          </Card>
        </div>


        <div className="stack">
          <Card>
            <CardHeader title="Estimated complexity" />
            <CardBody>
              <dl className="dl">
                <dt>Time</dt>
                <dd className="mono small">{complexity.time}</dd>
                <dt>Space</dt>
                <dd className="mono small">{complexity.space}</dd>
                <dt>Summary</dt>
                <dd className="small">{complexity.summary}</dd>
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Resource requirements" />
            <CardBody>
              <dl className="dl">
                <dt>CPU cores</dt>
                <dd>{resources.cpu_cores}</dd>
                <dt>Memory</dt>
                <dd>{resources.memory_gb} GB</dd>
                <dt>GPU</dt>
                <dd>{resources.gpu_required ? 'Required' : 'Not required'}</dd>
                <dt>Runtime</dt>
                <dd>{resources.expected_runtime}</dd>
              </dl>
              <p className="small muted mt-2">{resources.notes}</p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Baseline model" />
            <CardBody>
              <dl className="dl">
                <dt>Model</dt>
                <dd>{baseline?.name || '—'}</dd>
                <dt>Score</dt>
                <dd>{baseline?.summary || '—'}</dd>
                <dt>Training</dt>
                <dd>{formatSeconds(baseline?.training_time_sec)}</dd>
              </dl>
              <p className="small muted mt-2">{baseline?.role}</p>
            </CardBody>
          </Card>

          {classical.status === 'completed' ? (
            <Alert tone="info" title="These scores were measured on your data">
              Each model was trained on an 80% split and evaluated on a held-out 20%. They
              are a baseline reference, not a tuned best-in-class result.
            </Alert>
          ) : (
            <Alert tone="warning" title="No model was trained">
              {classical.summary}
            </Alert>
          )}

          <div className="row row--between">
            <Link to="/analysis">
              <Button variant="ghost" size="sm">Back</Button>
            </Link>
            <Link to="/quantum">
              <Button variant="primary" iconRight="arrowRight">Continue to Quantum Analysis</Button>
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}
