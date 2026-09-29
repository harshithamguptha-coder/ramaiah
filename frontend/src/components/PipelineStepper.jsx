/**
 * Pipeline stepper.
 *
 * Clicking a stage navigates to it. Stages that depend on data which does not
 * exist yet are rendered disabled so the flow order is always obvious.
 */

import { useNavigate } from 'react-router-dom'

export default function PipelineStepper({ pipeline = [], requireAnalysis = true, current = 0 }) {
  const navigate = useNavigate()

  return (
    <div className="stepper">
      {pipeline.map((stage, index) => {
        const reachable = !requireAnalysis || stage.status === 'completed' || index <= current
        return (
          <button
            key={stage.key}
            type="button"
            className={`step step--${stage.status}`}
            onClick={() => reachable && navigate(stage.route)}
            disabled={!reachable}
            title={stage.description}
            style={reachable ? undefined : { opacity: 0.55, cursor: 'not-allowed' }}
          >
            <span className="step__index">
              Stage {stage.order} · {stage.status}
            </span>
            <span className="step__label">{stage.label}</span>
          </button>
        )
      })}
    </div>
  )
}
