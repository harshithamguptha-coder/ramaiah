/** Dataset upload: drag-and-drop or browse, plus the optional problem statement. */

import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import { Alert, Badge, Button, Card, CardBody, CardHeader, MockBadge } from '../components/ui'
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
  const [dragging, setDragging] = useState(false)
  const [status, setStatus] = useState('idle') // idle | uploading | uploaded | analyzing
  const [error, setError] = useState(null)

  const extension = file ? `.${file.name.split('.').pop().toLowerCase()}` : ''

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
      await upload(file, description.trim())
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
      await startAnalysis(description.trim())
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
              actions={<MockBadge label="Heuristic (mock)" />}
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
              <Alert tone="warning" className="mt-4">
                Steps 3–5 currently return mocked values.
              </Alert>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  )
}
