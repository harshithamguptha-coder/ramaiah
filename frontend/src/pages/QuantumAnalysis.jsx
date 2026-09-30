/** Quantum Analysis: suitability score, candidate algorithms, resources, limits. */

import { Link } from 'react-router-dom'
import RequireAnalysis from '../components/RequireAnalysis'
import PipelineStepper from '../components/PipelineStepper'
import { Alert, Badge, Button, Card, CardBody, CardFooter, CardHeader, MeterRow, SourceBadge, StatTile } from '../components/ui'
import { BarChart, ScoreGauge } from '../components/charts'
import { useAnalysisContext } from '../context/AnalysisContext'

const SUITABILITY_TONE = { High: 'success', Moderate: 'warning', Low: 'danger' }

export default function QuantumAnalysis() {
  const { quantum, pipeline } = useAnalysisContext()

  return (
    <RequireAnalysis
      title="Quantum AI Analysis"
      subtitle="Pipeline stage 4 of 7 — quantum suitability, candidate algorithms and resource estimates."
      stage={quantum}
      stageLabel="Quantum AI analysis"
    >
      {quantum ? <QuantumStage quantum={quantum} pipeline={pipeline} /> : null}
    </RequireAnalysis>
  )
}

/** Stage body — see the note in ClassicalAnalysis.jsx about the split. */
function QuantumStage({ quantum, pipeline }) {
  const circuits = quantum.circuit_complexity
  const resources = quantum.estimated_resources

  return (
    <>
      <Card accent="quantum">
        <CardHeader
          title="Analysis pipeline"
          actions={<SourceBadge block={quantum} label="Factor model" />}
        />
        <CardBody>
          <PipelineStepper pipeline={pipeline} current={3} />
        </CardBody>
      </Card>

      <div className="grid grid--4">
        <Card accent="quantum">
          <CardHeader title="Quantum suitability" />
          <CardBody>
            <ScoreGauge
              score={quantum.suitability_score}
              label={quantum.suitability_label}
              tone={SUITABILITY_TONE[quantum.suitability_label] || 'quantum'}
            />
          </CardBody>
        </Card>
        <StatTile
          label="Qubits required"
          value={quantum.qubits_required}
          hint={`estimate ${quantum.qubits_estimate_range}`}
          tone="quantum"
        />
        <StatTile label="Circuit depth" value={circuits.depth} hint={`${circuits.gate_count} gates`} />
        <StatTile
          label="Feasibility"
          value={quantum.feasibility}
          hint={`confidence ${Math.round(quantum.confidence * 100)}%`}
        />
      </div>

      <div className="grid grid--sidebar">
        <div className="stack">
          <Card>
            <CardHeader
              title="Candidate quantum algorithms"
              subtitle={`Primary candidate: ${quantum.primary_algorithm}`}
              actions={<SourceBadge block={quantum} label="Scored" />}
            />
            <CardBody tight>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Algorithm</th>
                      <th>Family</th>
                      <th className="num">Qubits</th>
                      <th className="num">Depth</th>
                      <th className="num">Gates</th>
                      <th>Fit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quantum.candidate_algorithms.map((algo) => (
                      <tr key={algo.name}>
                        <td>
                          <div style={{ fontWeight: 650 }}>{algo.name}</div>
                          <div className="small muted">{algo.notes}</div>
                          {algo.blocking_issues?.length > 0 && (
                            <div className="small" style={{ color: 'var(--danger)' }}>
                              Blocked: {algo.blocking_issues.join(' ')}
                            </div>
                          )}
                        </td>
                        <td className="muted">{algo.family}</td>
                        <td className="num">{algo.qubits_required}</td>
                        <td className="num">{algo.circuit_depth}</td>
                        <td className="num">{algo.gate_count}</td>
                        <td>
                          <Badge
                            tone={
                              algo.suitability === 'high'
                                ? 'success'
                                : algo.suitability === 'medium'
                                  ? 'warning'
                                  : 'neutral'
                            }
                          >
                            {algo.suitability}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
            <CardFooter>{quantum.note}</CardFooter>
          </Card>

          <div className="grid grid--2">
            <Card>
              <CardHeader title="Potential advantages" />
              <CardBody>
                <ul className="small stack stack--sm">
                  {quantum.potential_advantages.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Limitations" />
              <CardBody>
                <ul className="small stack stack--sm">
                  {quantum.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          </div>
        </div>

        <div className="stack">
          <Card>
            <CardHeader title="Problem fitting" subtitle="Relative fit of each candidate for this problem." />
            <CardBody>
              <BarChart
                tone="quantum"
                suffix="%"
                data={quantum.candidate_algorithms.map((a) => ({
                  label: a.name.length > 22 ? `${a.name.slice(0, 21)}…` : a.name,
                  value: a.problem_fitting * 100,
                }))}
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Scoring factors"
              subtitle={quantum.scoring?.formula || 'Weighted sum of normalised factors.'}
            />
            <CardBody>
              <div className="stack stack--sm">
                {(quantum.scoring?.factors || []).map((factor) => (
                  <MeterRow
                    key={factor.key}
                    label={factor.label || factor.key}
                    value={(factor.normalised ?? 0) * 100}
                    tone={
                      factor.normalised >= 0.66 ? 'success' : factor.normalised >= 0.33 ? 'warning' : 'danger'
                    }
                    displayValue={`${Math.round((factor.normalised ?? 0) * 100)}% × ${factor.weight}`}
                  />
                ))}
              </div>
              {quantum.scoring?.caps_applied?.length > 0 && (
                <div className="mt-4">
                  <div className="stat__label mb-2">Hard caps applied</div>
                  <ul className="small stack stack--sm">
                    {quantum.scoring.caps_applied.map((cap) => (
                      <li key={cap.cap}>
                        Capped at {cap.cap}/100 — {cap.why}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="small muted mt-2">
                Raw score {quantum.scoring?.raw_score}/100 before caps.
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Circuit complexity" />
            <CardBody>
              <dl className="dl">
                <dt>Depth</dt>
                <dd>{circuits.depth}</dd>
                <dt>Gate count</dt>
                <dd>{circuits.gate_count.toLocaleString()}</dd>
                <dt>2-qubit gate ratio</dt>
                <dd>{Math.round(circuits.two_qubit_gate_ratio * 100)}%</dd>
                <dt>Summary</dt>
                <dd className="small">{circuits.summary}</dd>
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Estimated quantum resources" />
            <CardBody>
              <dl className="dl">
                <dt>Provider</dt>
                <dd>{resources.provider}</dd>
                <dt>Qubits</dt>
                <dd>{resources.required_qubits}</dd>
                <dt>Queue time</dt>
                <dd>{resources.expected_queue_time}</dd>
                <dt>Shots</dt>
                <dd>{resources.shots.toLocaleString()}</dd>
                <dt>Cost / shot</dt>
                <dd>{resources.cost_per_shot}</dd>
              </dl>
              <p className="small muted mt-2">{resources.notes}</p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Encoding strategies" />
            <CardBody>
              <div className="chip-row">
                {quantum.encoding_strategies.map((strategy) => (
                  <span className="chip" key={strategy}>
                    {strategy}
                  </span>
                ))}
              </div>
            </CardBody>
          </Card>

          <Alert tone="info" title="This is a suitability analysis, not an experiment">
            {quantum.score_interpretation ||
              'No quantum circuit was built or executed. The score above measures how worth investigating quantum methods are, not how well they would perform.'}
          </Alert>

          <div className="row row--between">
            <Link to="/classical">
              <Button variant="ghost" size="sm">Back</Button>
            </Link>
            <Link to="/comparison">
              <Button variant="primary" iconRight="arrowRight">Continue to Comparison</Button>
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}

