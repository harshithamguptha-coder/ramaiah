/** Landing dashboard: overview, recent analyses and approach status cards. */

import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import { Alert, Badge, Button, Card, CardBody, CardHeader, EmptyState, LoadingBlock, StatTile } from '../components/ui'
import { useAnalysisContext } from '../context/AnalysisContext'
import { useAsync } from '../hooks/useAsync'
import api from '../services/api'
import { formatDateTime, relativeTime, truncate } from '../utils/format'

const APPROACHES = [
  {
    key: 'classical',
    name: 'Classical AI',
    tone: 'classical',
    status: 'Available',
    badge: 'Ready',
    blurb: 'Mature, well-understood models. Production-ready for most tabular problems today.',
  },
  {
    key: 'quantum',
    name: 'Quantum AI',
    tone: 'quantum',
    status: 'Experimental',
    badge: 'Limited',
    blurb: 'Variational and kernel methods. Restricted to small feature spaces on current hardware.',
  },
  {
    key: 'hybrid',
    name: 'Hybrid AI',
    tone: 'hybrid',
    status: 'Recommended',
    badge: 'Practical',
    blurb: 'Classical backbone with a quantum sub-step. Keeps a safe fallback path.',
  },
]

const STAGES = [
  ['1', 'Upload Dataset', 'CSV / XLSX / JSON ingestion'],
  ['2', 'Problem Analysis', 'Shape, types, target column'],
  ['3', 'Classical Analysis', 'Candidate models & baseline'],
  ['4', 'Quantum Analysis', 'Suitability & circuit estimates'],
  ['5', 'Comparison', 'Weighted three-way matrix'],
  ['6', 'Recommendation', 'Approach with reasoning'],
  ['7', 'Detailed Report', 'Consolidated document'],
]

export default function Dashboard() {
  const { analysis, isComplete, recommendation, classical, quantum } = useAnalysisContext()
  const { data, loading, error } = useAsync(() => api.listAnalyses(5), [])

  const recent = data?.items ?? []
  const hasAnalysis = Boolean(analysis?.dataset?.file_name)

  return (
    <div className="stack">
      <PageHeader
        title="Q-Compass"
        subtitle="Quantum Readiness & AI Decision Engine — analyse an AI/ML problem and decide whether it is better suited to Classical AI, Quantum AI, or a Hybrid approach."
        actions={
          <>
            <Link to="/upload">
              <Button variant="primary" icon="upload" iconRight="arrowRight">
                Upload Dataset
              </Button>
            </Link>
            {isComplete && (
              <Link to="/report">
                <Button variant="secondary" icon="report">
                  View Latest Report
                </Button>
              </Link>
            )}
          </>
        }
      />

      <Alert tone="info" title="Decision support, not a quantum advocate">
        Dataset statistics and the classical baseline are <strong>measured</strong> on your
        data. The quantum score is a <strong>theoretical suitability analysis</strong>: it
        estimates how worth investigating quantum methods are, not how well they would
        perform. No quantum circuit is executed, and the recommendation defaults to Classical
        AI unless the problem earns otherwise.
      </Alert>

      <Card accent="accent">
        <CardHeader title="Analysis pipeline" subtitle="Seven stages from raw dataset to a downloadable report." />
        <CardBody>
          <div className="grid grid--4">
            {STAGES.map(([num, title, blurb]) => (
              <div className="stat" key={num}>
                <span className="stat__label">Stage {num}</span>
                <span style={{ fontWeight: 650, color: 'var(--ink-800)' }}>{title}</span>
                <span className="stat__hint">{blurb}</span>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>


      <div>
        <div className="row row--between mb-2">
          <h2>Approach readiness</h2>
          <span className="small muted">General capability, not dataset-specific</span>
        </div>
        <div className="grid grid--3">
          {APPROACHES.map((approach) => (
            <Card key={approach.key} accent={approach.tone}>
              <CardHeader
                title={approach.name}
                subtitle={approach.status}
                actions={<Badge tone={approach.tone}>{approach.badge}</Badge>}
              />
              <CardBody>
                <p className="small">{approach.blurb}</p>
              </CardBody>
            </Card>
          ))}
        </div>
      </div>

      {hasAnalysis && (
        <Card accent="accent">
          <CardHeader
            title="Active analysis"
            subtitle={analysis.dataset.file_name}
            actions={
              <>
                <Badge tone={isComplete ? 'success' : 'info'}>{isComplete ? 'Complete' : 'Uploaded'}</Badge>
                <Badge tone="success" title="Produced by the real analysis engine.">Real analysis</Badge>
              </>
            }
          />
          <CardBody>
            <div className="grid grid--4">
              <StatTile label="Rows" value={analysis.dataset.rows ?? '—'} />
              <StatTile label="Columns" value={analysis.dataset.column_count ?? '—'} />
              <StatTile
                label="Classical best"
                value={classical?.best_model?.summary || (classical ? 'Not evaluated' : '—')}
                hint={classical?.best_model?.name}
              />
              <StatTile
                label="Quantum suitability"
                value={quantum ? `${quantum.suitability_score}/100` : '—'}
                hint={quantum?.suitability_label}
                tone="quantum"
              />
            </div>

            {recommendation && (
              <div className="row row--between mt-4">
                <div>
                  <span className="stat__label">Recommended approach</span>
                  <div style={{ fontWeight: 700, fontSize: 'var(--text-lg)' }}>
                    {recommendation.recommended_approach}
                  </div>
                </div>
                <Link to="/recommendation">
                  <Button variant="primary" iconRight="arrowRight">
                    View recommendation
                  </Button>
                </Link>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Recent analyses"
          subtitle={loading ? 'Loading…' : `${recent.length} stored in this session`}
        />
        <CardBody tight>
          {loading ? (
            <LoadingBlock label="Fetching recent analyses…" />
          ) : error ? (
            <Alert tone="danger" title="Could not load recent analyses">
              {error}
            </Alert>
          ) : recent.length === 0 ? (
            <EmptyState
              icon="database"
              title="No analyses yet"
              action={
                <Link to="/upload">
                  <Button variant="primary" icon="upload">
                    Upload your first dataset
                  </Button>
                </Link>
              }
            >
              Upload a CSV, XLSX or JSON dataset to start your first Q-Compass analysis.
            </EmptyState>
          ) : (
            <div className="stack stack--sm">
              {recent.map((item) => (
                <div className="file-chip" key={item.analysis_id}>
                  <div className="file-chip__icon">
                    <Badge tone="neutral">{String(item.file_name).split('.').pop()}</Badge>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="file-chip__name">{item.file_name}</div>
                    <div className="small muted">
                      {item.task_type} · {truncate(item.problem_description, 70) || 'No problem described'}
                    </div>
                    <div className="small muted">
                      {formatDateTime(item.created_at)} · {relativeTime(item.created_at)}
                    </div>
                  </div>
                  <Badge tone="success">{item.recommended_approach}</Badge>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
