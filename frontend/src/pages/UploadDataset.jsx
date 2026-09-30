/** Dataset upload: drag-and-drop or browse, plus the optional problem statement. */

import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import { Alert, Badge, Button, Card, CardBody, CardHeader } from '../components/ui'
import Icon from '../components/ui/Icon'
import { useAnalysisContext } from '../context/AnalysisContext'
import { ACCEPTED_FILE_TYPES, MAX_UPLOAD_MB, PROBLEM_PLACEHOLDER } from '../constants/navigation'
import { formatBytes } from '../utils/format'

export default function UploadDataset() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const { upload, startAnalysis, analysis, reset } = useAnalysisContext()

  const [file, setFile] = useState(null)
  const [description, setDescription] = useState('')
  const [targetColumn, setTargetColumn] = useState('')
  const [dragging, setDragging] = useState(false)
  const [status, setStatus] = useState('idle') // idle | uploading | uploaded | analyzing
  const [error, setError] = useState(null)

  const extension = file ? `.${file.name.split('.').pop().toLowerCase()}` : ''
  // What the backend auto-detected, used to prefill the hint and the placeholder.
  const detectedTarget = analysis?.dataset?.target_column || ''

/** Shown while the single backend pass is running. */
const ANALYSIS_STAGES = [
  'Analyzing dataset',
  'Characterising the problem',
  'Training classical baselines',
  'Scoring quantum suitability',
  'Comparing approaches',
  'Generating recommendation',
  'Generating report',
]

  /** Client-side validation mirrors the backend rules for instant feedback. */
  function validate(candidate) {
    const ext = `.${candidate.name.split('.').pop().toLowerCase()}`
    if (!ACCEPTED_FILE_TYPES.includes(ext)) {
      return `Unsupported file type "${ext}". Allowed: ${ACCEPTED_FILE_TYPES.join(', ')}`
    }
    if (candidate.size > MAX_UPLOAD_MB * 1024 * 1024) {
      return `File is larger than the ${MAX_UPLOAD_MB} MB limit.`
    }
    if (candidate.size === 0) return 'The selected file is empty.'
    return null
  }

  function selectFile(candidate) {
    if (!candidate) return
    const problem = validate(candidate)
    setError(problem)
    if (!problem) {
      setFile(candidate)
      setStatus('idle')
    }
  }

  function clearFile() {
    setFile(null)
    setStatus('idle')
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
    reset()
  }

  async function handleUpload() {
    if (!file || error) return
    setStatus('uploading')
    setError(null)
    try {
      const result = await upload(file, description.trim(), targetColumn.trim())
      console.log('[Q-Compass] UPLOAD ANALYSIS ID:', result.analysis_id)
      setStatus('uploaded')
    } catch (err) {
      setError(err.message)
      setStatus('idle')
    }
  }

  async function handleStartAnalysis() {
    setStatus('analyzing')
    setError(null)
    try {
      // The completed response *is* the analysis; the context adopts its id, so
      // there is no second fetch and the two ids cannot disagree.
      const completed = await startAnalysis(description.trim(), targetColumn.trim())
      console.log('[Q-Compass] ANALYZE RESPONSE ID:', completed.analysis_id)
      console.log('[Q-Compass] NAVIGATING TO: /analysis (id =', completed.analysis_id, ')')
      navigate('/analysis')
    } catch (err) {
      setError(err.message)
      setStatus('uploaded')
    }
  }

  const busy = status === 'uploading' || status === 'analyzing'


  return (
    <div className="stack">
      <PageHeader
        title="Upload Dataset"
        subtitle="Provide a CSV, XLSX or JSON file and describe the AI problem you want to solve."
      />

      {error && (
        <Alert tone="danger" title="Upload problem">
          {error}
        </Alert>
      )}

      <div className="grid grid--sidebar">
        <div className="stack">
          <Card>
            <CardHeader title="1. Dataset file" subtitle="Structural profiling runs on upload." />
            <CardBody>
              {!file ? (
                <div
                  className={`dropzone${dragging ? ' is-dragging' : ''}`}
                  onClick={() => inputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragging(true)
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault()
                    setDragging(false)
                    selectFile(e.dataTransfer.files?.[0])
                  }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
                >
                  <Icon name="upload" size={30} className="dropzone__icon" />
                  <div className="dropzone__title">Drop a dataset here, or click to browse</div>
                  <p className="small muted mt-2">
                    Supported formats: {ACCEPTED_FILE_TYPES.join(', ')} · up to {MAX_UPLOAD_MB} MB
                  </p>
                </div>
              ) : (
                <div className="stack stack--sm">
                  <div className="file-chip">
                    <div className="file-chip__icon">
                      <Icon name="file" size={19} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="file-chip__name">{file.name}</div>
                      <div className="small muted">
                        {formatBytes(file.size)} · {extension.replace('.', '').toUpperCase()}
                      </div>
                    </div>
                    <Badge tone={status === 'idle' ? 'neutral' : 'success'}>
                      {status === 'idle' ? 'Ready' : status === 'uploading' ? 'Uploading…' : 'Uploaded'}
                    </Badge>
                    <Button size="sm" variant="ghost" onClick={clearFile} disabled={busy} aria-label="Remove file">
                      <Icon name="trash" size={15} />
                    </Button>
                  </div>

                  {status === 'uploaded' && (
                    <Alert tone="success" title="Dataset received">
                      {file.name} was uploaded successfully. Press <strong>Start Analysis</strong> to
                      run the pipeline.
                    </Alert>
                  )}

                  {analysis?.dataset?.profiled && (
                    <div className="small muted">
                      Profiled: {analysis.dataset.rows} rows · {analysis.dataset.column_count} columns
                      {analysis.dataset.target_column ? ` · target "${analysis.dataset.target_column}"` : ''}
                    </div>
                  )}
                </div>
              )}

              <input
                ref={inputRef}
                type="file"
                accept={ACCEPTED_FILE_TYPES.join(',')}
                onChange={(e) => selectFile(e.target.files?.[0])}
                style={{ display: 'none' }}
                aria-label="Select dataset file"
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="2. Describe your AI problem"
              subtitle="Optional, but it improves the task-type inference."
            />
            <CardBody>
              <div className="field">
                <label className="field__label" htmlFor="problem-description">
                  Problem statement <span className="field__optional">(optional)</span>
                </label>
                <textarea
                  id="problem-description"
                  className="textarea"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={PROBLEM_PLACEHOLDER}
                  maxLength={2000}
                  rows={4}
                />
                <span className="field__hint">
                  {description.length}/2000 characters. Used to infer the learning task type.
                </span>
              </div>

              <div className="field mt-4">
                <label className="field__label" htmlFor="target-column">
                  Target column <span className="field__optional">(optional)</span>
                </label>
                <input
                  id="target-column"
                  className="input"
                  list="uploaded-columns"
                  value={targetColumn}
                  onChange={(e) => setTargetColumn(e.target.value)}
                  placeholder={detectedTarget || 'e.g. quality'}
                  maxLength={200}
                />
                <datalist id="uploaded-columns">
                  {(analysis?.dataset?.column_names || []).map((name) => (
                    <option key={name} value={name} />
                  ))}
                </datalist>
                <span className="field__hint">
                  {analysis?.dataset?.target_column
                    ? `Auto-detected "${analysis.dataset.target_column}". Set this only if that is wrong.`
                    : 'No target column was auto-detected. Name the column you want to predict - without it the classical stage cannot be evaluated.'}
                </span>
              </div>
            </CardBody>
          </Card>
        </div>


        <div className="stack">
          <Card accent="accent">
            <CardHeader title="3. Start analysis" />
            <CardBody>
              <p className="small mb-2">
                Uploading stores the file and reads its shape. Starting the analysis runs the
                remaining pipeline stages and moves you to the problem analysis page.
              </p>

              <div className="stack stack--sm">
                <Button
                  variant="primary"
                  block
                  icon="upload"
                  loading={status === 'uploading'}
                  disabled={!file || busy}
                  onClick={handleUpload}
                >
                  {status === 'uploaded' ? 'Re-upload' : 'Upload Dataset'}
                </Button>

                <Button
                  variant="secondary"
                  block
                  icon="arrowRight"
                  loading={status === 'analyzing'}
                  disabled={status !== 'uploaded' || busy}
                  onClick={handleStartAnalysis}
                >
                  Start Analysis
                </Button>
              </div>
            </CardBody>
          </Card>

          {status === 'analyzing' && (
            <Card accent="accent" className="mt-4">
              <CardHeader title="Running the analysis pipeline" />
              <CardBody>
                <ol className="small stage-progress">
                  {ANALYSIS_STAGES.map((label, index) => (
                    <li key={label} className={index === 0 ? 'is-current' : 'is-pending'}>
                      <span className="stage-progress__mark" aria-hidden="true">
                        {index === 0 ? '›' : '·'}
                      </span>
                      {label}
                    </li>
                  ))}
                </ol>
                <p className="small muted mt-2">
                  The backend runs every stage in one pass. This page will open automatically once
                  it finishes.
                </p>
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader title="What happens next" />
            <CardBody>
              <ol className="small stack stack--sm" style={{ paddingLeft: '1.1rem' }}>
                <li>Dataset profiling reads rows, columns, feature types and missing values.</li>
                <li>Problem classification infers the learning task type.</li>
                <li>Classical and quantum analyses produce comparison inputs.</li>
                <li>A weighted comparison yields the recommended approach.</li>
                <li>The report consolidates everything into a downloadable document.</li>
              </ol>
              <Alert tone="info" className="mt-4">
                Steps 1–2 are measured from your file. Steps 3–5 are computed by the analysis
                engine; the quantum stage is a suitability analysis, not an executed circuit.
              </Alert>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  )
}
