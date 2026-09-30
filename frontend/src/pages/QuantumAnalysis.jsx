/** Quantum Analysis: suitability score, candidate algorithms, resources, limits. */

import { Link } from 'react-router-dom'
import RequireAnalysis from '../components/RequireAnalysis'
import PipelineStepper from '../components/PipelineStepper'
import { Alert, Badge, Button, Card, CardBody, CardFooter, CardHeader, StatTile } from '../components/ui'
import { BarChart, ScoreGauge } from '../components/charts'
import { useAnalysisContext } from '../context/AnalysisContext'

const SUITABILITY_TONE = { High: 'success', Moderate: 'warning', Low: 'danger' }

export default function QuantumAnalysis() {
  const { quantum, pipeline } = useAnalysisContext()

  const circuits = quantum?.circuit_complexity ?? {}
  const resources = quantum?.estimated_resources ?? {}
  const execution = quantum?.execution ?? {}
  const executed = quantum?.status === 'completed'
  const realExecution = quantum?.quantum_analysis_real === true
  const dataSourceLabel = quantum?.data_source === 'real' ? 'Real' : quantum?.data_source === 'unavailable' ? 'Unavailable' : quantum?.data_source || 'Unknown'

  return (
    <RequireAnalysis
      title="Quantum AI Analysis"
      subtitle="Pipeline stage 4 of 7 — quantum suitability, candidate algorithms and resource estimates."
      stage={quantum}
      stageLabel="Quantum AI analysis"
    >
      {quantum ? (
        <>
      <Card accent="quantum">
        <CardHeader title="Analysis pipeline" actions={<Badge tone={realExecution ? 'success' : 'warning'}>{realExecution ? 'Real local Qiskit execution' : 'Quantum execution unavailable'}</Badge>} />
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
          label="Execution time"
          value={executed ? `${execution.execution_time_sec}s` : '—'}
          hint={executed ? `${execution.shots?.toLocaleString()} local shots` : 'No result'}
        />
      </div>

      <div className="grid grid--sidebar">
        <div className="stack">
          <Card>
            <CardHeader
              title="Candidate quantum algorithms"
              subtitle={`Primary candidate: ${quantum.primary_algorithm}`}
              actions={<Badge tone={executed ? 'success' : 'warning'}>{quantum.status}</Badge>}
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
            <CardHeader title="Measured QAOA result" />
            <CardBody>
              <dl className="dl">
                <dt>Status</dt>
                <dd>{quantum.status}</dd>
                <dt>Data source</dt>
                <dd>{dataSourceLabel}</dd>
                <dt>Objective / cost</dt>
                <dd>{execution.objective_value ?? '—'}</dd>
                <dt>Expected objective</dt>
                <dd>{execution.expected_objective_value ?? '—'}</dd>
                <dt>Parameter trials</dt>
                <dd>{execution.iterations ?? 0}</dd>
                <dt>Highest-probability graph partition</dt>
                <dd className="mono small">{execution.best_partition_bitstring ?? execution.best_bitstring ?? '—'}</dd>
              </dl>
              {execution.features?.length ? <p className="small muted mt-2">Feature graph: {execution.features.join(', ')}</p> : null}
              <p className="small muted mt-2">{execution.partition_interpretation}</p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Circuit complexity" />
            <CardBody>
              <dl className="dl">
                <dt>Depth</dt>
                <dd>{circuits.depth}</dd>
                <dt>Gate count</dt>
                <dd>{(circuits.gate_count ?? 0).toLocaleString()}</dd>
                <dt>2-qubit gate ratio</dt>
                <dd>{Math.round(circuits.two_qubit_gate_ratio * 100)}%</dd>
                <dt>Feasibility</dt>
                <dd>{quantum.feasibility}</dd>
                <dt>Summary</dt>
                <dd className="small">{circuits.summary}</dd>
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Suitability decision" subtitle={quantum.recommended_approach} />
            <CardBody>
              <ul className="small stack stack--sm">
                {(quantum.suitability?.reasons || []).map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
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
                <dd>{(resources.shots ?? 0).toLocaleString()}</dd>
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

          <Alert tone={executed ? 'warning' : 'danger'} title={executed ? 'Interpret results carefully' : 'Quantum execution unavailable'}>
            {executed
              ? 'This is a real local simulator measurement for a QAOA-based feature-relationship optimisation / feature-selection experiment. The partition is not a final selected-feature subset and does not demonstrate quantum advantage.'
              : (quantum.error || 'The circuit could not be executed for this input. Classical computing is recommended.')}
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
      ) : null}
    </RequireAnalysis>
  )
}
