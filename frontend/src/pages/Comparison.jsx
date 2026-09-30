/** Comparison: Classical AI vs Quantum AI vs Hybrid AI across weighted criteria. */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import RequireAnalysis from '../components/RequireAnalysis'
import PipelineStepper from '../components/PipelineStepper'
import { Alert, Badge, Button, Card, CardBody, CardFooter, CardHeader, SourceBadge } from '../components/ui'
import { GroupedBars, RadarChart, TONE_VAR } from '../components/charts'
import { useAnalysisContext } from '../context/AnalysisContext'

const KEYS = ['classical', 'quantum', 'hybrid']
const LABELS = { classical: 'Classical AI', quantum: 'Quantum AI', hybrid: 'Hybrid AI' }
const DESCRIPTIONS = {
  classical: 'Conventional ML on commodity hardware. Fast, reliable and fully deployable today.',
  quantum: 'Circuit-based models on QPUs or simulators. Constrained by qubit counts and noise.',
  hybrid: 'Classical backbone with a quantum sub-step, and a classical fallback if it fails.',
}

export default function Comparison() {
  const { comparison, pipeline } = useAnalysisContext()
  const [view, setView] = useState('table')

  return (
    <RequireAnalysis
      title="Classical vs Quantum Comparison"
      subtitle="Pipeline stage 5 of 7 — a weighted comparison of Classical AI, Quantum AI and Hybrid AI."
      stage={comparison}
      stageLabel="Comparison"
    >
      {comparison ? <ComparisonStage comparison={comparison} pipeline={pipeline} view={view} setView={setView} /> : null}
    </RequireAnalysis>
  )
}

/** Stage body — see the note in ClassicalAnalysis.jsx about the split. */
function ComparisonStage({ comparison, pipeline, view, setView }) {
  const {
    criteria,
    weighted_scores: scores,
    winner,
    radar_axes: axes,
    radar_series: series,
  } = comparison

  return (
    <>
      <Card accent="accent">
        <CardHeader
          title="Analysis pipeline"
          actions={
            <div className="row row--tight">
              <Button size="sm" variant={view === 'table' ? 'primary' : 'secondary'} onClick={() => setView('table')}>
                Table
              </Button>
              <Button size="sm" variant={view === 'chart' ? 'primary' : 'secondary'} onClick={() => setView('chart')}>
                Charts
              </Button>
            </div>
          }
        />
        <CardBody>
          <PipelineStepper pipeline={pipeline} current={4} />
        </CardBody>
      </Card>

      <div className="grid grid--3">
        {KEYS.map((key) => (
          <div
            className={`approach-card approach-card--${key}${winner === key ? ' approach-card--winner' : ''}`}
            key={key}
          >
            <div className="row row--between">
              <span className="approach-card__name">{LABELS[key]}</span>
              {winner === key && <Badge tone="success">Winner</Badge>}
            </div>
            <div className="stat__value" style={{ color: TONE_VAR[key] }}>
              {scores[key]}
              <span className="small muted" style={{ fontWeight: 400 }}> / 100</span>
            </div>
            <p className="small muted">{DESCRIPTIONS[key]}</p>
          </div>
        ))}
      </div>

      {view === 'table' ? (
        <Card>
          <CardHeader
            title="Weighted comparison matrix"
            subtitle="Each criterion is scored 0–100 and multiplied by its weight. Higher is better. Hover a cell to see whether it is measured, derived, or an assumption."
            actions={<SourceBadge block={comparison} label="Weighted matrix" />}
          />
          <CardBody tight>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Criterion</th>
                    <th className="num">Weight</th>
                    <th className="col-classical num">Classical AI</th>
                    <th className="col-quantum num">Quantum AI</th>
                    <th className="col-hybrid num">Hybrid AI</th>
                  </tr>
                </thead>
                <tbody>
                  {criteria.map((row) => {
                    const bestKey = KEYS.reduce((a, b) => (row[a].score >= row[b].score ? a : b))
                    return (
                      <tr key={row.criterion}>
                        <td style={{ fontWeight: 650 }}>{row.criterion}</td>
                        <td className="num muted">{Math.round(row.weight * 100)}%</td>
                        {KEYS.map((key) => (
                          <td
                            key={key}
                            className={`num${bestKey === key ? ' best' : ''}`}
                            title={`${row[key].note}${row[key].basis ? ` (${row[key].basis})` : ''}`}
                          >
                            <div style={{ fontWeight: 650 }}>{row[key].score}</div>
                            <div className="small muted">{row[key].value}</div>
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                  <tr>
                    <td style={{ fontWeight: 700 }}>Weighted total</td>
                    <td className="num muted">100%</td>
                    {KEYS.map((key) => (
                      <td key={key} className={`num${winner === key ? ' best' : ''}`} style={{ fontWeight: 700 }}>
                        {scores[key]}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </CardBody>
          <CardFooter>{comparison.note}</CardFooter>
        </Card>
      ) : (
        <div className="grid grid--2">
          <Card>
            <CardHeader title="Score profile by criterion" />
            <CardBody>
              <GroupedBars criteria={criteria} keys={KEYS} />
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Overall shape" subtitle="Higher is better on every axis." />
            <CardBody>
              <RadarChart axes={axes} series={series} />
            </CardBody>
          </Card>
        </div>
      )}

      <Alert tone="info" title={comparison.summary} />

      <div className="row row--between">
        <Link to="/quantum">
          <Button variant="ghost" size="sm">Back</Button>
        </Link>
        <Link to="/recommendation">
          <Button variant="primary" iconRight="arrowRight">Continue to Recommendation</Button>
        </Link>
      </div>
    </>
  )
}

