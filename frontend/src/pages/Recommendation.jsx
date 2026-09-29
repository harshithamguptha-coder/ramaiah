/** Recommendation: the headline verdict with reasons, advantages, limits and next steps. */

import { Link } from 'react-router-dom'
import RequireAnalysis from '../components/RequireAnalysis'
import PipelineStepper from '../components/PipelineStepper'
import { Alert, Badge, Button, Card, CardBody, CardHeader, MockBadge, ProgressBar } from '../components/ui'
import { useAnalysisContext } from '../context/AnalysisContext'

export default function Recommendation() {
  const { recommendation, pipeline } = useAnalysisContext()
  if (!recommendation) return null

  const tone = recommendation.approach_key

  return (
    <RequireAnalysis
      title="Recommendation"
      subtitle="Pipeline stage 6 of 7 — the recommended approach, the reasoning behind it, and what to do next."
    >
      <Card accent="accent">
        <CardHeader title="Analysis pipeline" actions={<MockBadge label="Mock decision engine" />} />
        <CardBody>
          <PipelineStepper pipeline={pipeline} current={5} />
        </CardBody>
      </Card>

      <div className={`rec-hero rec-hero--${tone}`}>
        <div className="row row--between" style={{ alignItems: 'flex-start' }}>
          <div>
            <span className="badge rec-hero__badge">
              <span className="dot" />
              Placeholder recommendation
            </span>
            <h2 className="mt-2">{recommendation.headline}</h2>
            <p style={{ maxWidth: '62ch' }}>{recommendation.summary}</p>
          </div>
          <div className="text-right">
            <div className="stat__label" style={{ color: 'rgba(255,255,255,0.8)' }}>
              Confidence
            </div>
            <div style={{ fontSize: '2.5rem', fontWeight: 750, lineHeight: 1 }}>
              {Math.round(recommendation.confidence * 100)}%
            </div>
            <div className="small" style={{ color: 'rgba(255,255,255,0.85)' }}>
              {recommendation.confidence_label}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid--3">
        {Object.entries(recommendation.scores || {}).map(([key, value]) => (
          <Card key={key}>
            <CardBody>
              <div className="stat__label mb-2">
                {key === 'classical' ? 'Classical AI' : key === 'quantum' ? 'Quantum AI' : 'Hybrid AI'}
              </div>
              <div className="stat__value">{value}</div>
              <div className="mt-2">
                <ProgressBar
                  value={value}
                  tone={value >= 85 ? 'success' : value >= 60 ? 'warning' : 'danger'}
                  label="Weighted score"
                />
              </div>
            </CardBody>
          </Card>
        ))}
      </div>


      <div className="grid grid--sidebar">
        <div className="stack">
          <Card>
            <CardHeader title="Main reasons" subtitle="Why this approach leads the comparison." />
            <CardBody>
              <div className="stack">
                {recommendation.reasons.map((reason) => (
                  <div className="stat" key={reason.title}>
                    <div className="row row--between">
                      <strong>{reason.title}</strong>
                      <Badge tone={reason.impact === 'High' ? 'warning' : 'neutral'}>{reason.impact} impact</Badge>
                    </div>
                    <p className="small">{reason.detail}</p>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>

          <div className="grid grid--2">
            <Card>
              <CardHeader title="Advantages" />
              <CardBody>
                <ul className="small stack stack--sm">
                  {recommendation.advantages.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Limitations" />
              <CardBody>
                <ul className="small stack stack--sm">
                  {recommendation.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          </div>
        </div>

        <div className="stack">
          <Card accent={tone}>
            <CardHeader title="Suggested next step" />
            <CardBody>
              <ol className="small stack stack--sm" style={{ paddingLeft: '1.1rem' }}>
                {recommendation.suggested_next_steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Implementation roadmap" />
            <CardBody>
              <div className="stack stack--sm">
                {recommendation.roadmap.map((phase) => (
                  <div className="row row--between" key={phase.phase}>
                    <span className="small">
                      <strong>{phase.phase}</strong> · {phase.title}
                    </span>
                    <Badge tone="neutral">{phase.status}</Badge>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Decision basis" />
            <CardBody>
              <p className="small">{recommendation.decision_basis}</p>
              <p className="small muted mt-2">{recommendation.confidence_in_underlying_data}</p>
            </CardBody>
          </Card>

          <Alert tone="warning" title="This is not a real recommendation">
            {recommendation.disclaimer}
          </Alert>

          <div className="row row--between">
            <Link to="/comparison">
              <Button variant="ghost" size="sm">
                Back
              </Button>
            </Link>
            <Link to="/report">
              <Button variant="primary" iconRight="arrowRight">
                View Detailed Report
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </RequireAnalysis>
  )
}

