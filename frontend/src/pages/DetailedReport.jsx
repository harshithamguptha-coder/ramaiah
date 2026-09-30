/** Detailed Report: renders the nine report sections assembled by the backend. */

import { Link } from 'react-router-dom'
import RequireAnalysis from '../components/RequireAnalysis'
import PipelineStepper from '../components/PipelineStepper'
import { Alert, Badge, Button, Card, CardBody, CardHeader, SourceBadge } from '../components/ui'
import { useAnalysisContext } from '../context/AnalysisContext'
import api from '../services/api'
import { formatDateTime } from '../utils/format'

/** Render one structured block from the report payload. */
function ReportBlock({ block }) {
  if (block.type === 'text') return <p className="small">{block.body}</p>

  if (block.type === 'callout') {
    return <Alert tone={block.tone === 'warning' ? 'warning' : 'info'}>{block.body}</Alert>
  }

  if (block.type === 'list') {
    const Tag = block.ordered ? 'ol' : 'ul'
    return (
      <Tag className="small stack stack--sm" style={{ paddingLeft: '1.2rem' }}>
        {block.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </Tag>
    )
  }

  if (block.type === 'table') {
    return (
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              {block.header.map((cell) => (
                <th key={cell}>{cell}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, index) => (
              <tr key={`${row[0]}-${index}`}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className={cellIndex === 0 ? '' : 'num'}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return null
}

export default function DetailedReport() {
  const { report, pipeline, analysisId, reset } = useAnalysisContext()

  return (
    <RequireAnalysis
      title="Detailed Report"
      subtitle="Pipeline stage 7 of 7 — the consolidated analysis, ready to download."
      stage={report}
      stageLabel="Detailed report"
    >
      {report ? <ReportStage report={report} pipeline={pipeline} analysisId={analysisId} reset={reset} /> : null}
    </RequireAnalysis>
  )
}

/** Stage body — see the note in ClassicalAnalysis.jsx about the split. */
function ReportStage({ report, pipeline, analysisId, reset }) {
  return (
    <>
      <Card accent="accent">
        <CardHeader title="Analysis pipeline" actions={<SourceBadge block={report} label="Generated" />} />
        <CardBody>
          <PipelineStepper pipeline={pipeline} current={6} />
        </CardBody>
      </Card>

      <div className="row row--between">
        <div>
          <div className="stat__label">Analysis ID</div>
          <div className="mono small">{analysisId}</div>
        </div>
        <div className="page-actions">
          <Button
            variant="primary"
            icon="download"
            onClick={() => {
              window.location.href = api.reportDownloadUrl(analysisId)
            }}
          >
            Download Report
          </Button>
          <Link to="/upload">
            <Button variant="secondary" icon="plus" onClick={reset}>
              Start New Analysis
            </Button>
          </Link>
        </div>
      </div>

      <Alert tone="info" title="What this report contains">
        Dataset statistics and the classical baseline are measured on your data. The quantum
        section is a suitability analysis with its full factor breakdown — no circuit was
        executed. The download is a Markdown export of exactly what is shown here.
      </Alert>

      <div className="grid grid--sidebar">
        <div className="stack">
          {report.sections.map((section, index) => (
            <Card key={section.key} id={`section-${section.key}`}>
              <CardHeader
                title={`${index + 1}. ${section.title}`}
                actions={<Badge tone="neutral">Section {index + 1}</Badge>}
              />
              <CardBody>
                <div className="stack">
                  {section.blocks.map((block, blockIndex) => (
                    <ReportBlock key={blockIndex} block={block} />
                  ))}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>

        <div className="stack">
          <Card className="report-toc">
            <CardHeader title="Contents" />
            <CardBody tight>
              {report.sections.map((section, index) => (
                <a
                  key={section.key}
                  className="report-toc__link"
                  href={`#section-${section.key}`}
                >
                  {index + 1}. {section.title}
                </a>
              ))}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Report details" />
            <CardBody>
              <dl className="dl">
                <dt>Title</dt>
                <dd className="small">{report.title}</dd>
                <dt>Generated</dt>
                <dd className="small">{formatDateTime(report.generated_at)}</dd>
                <dt>Sections</dt>
                <dd>{report.sections.length}</dd>
                <dt>Format</dt>
                <dd>Markdown (.md)</dd>
                <dt>Data source</dt>
                <dd>Real analysis</dd>
              </dl>
            </CardBody>
          </Card>

          <div className="row row--between">
            <Link to="/recommendation">
              <Button variant="ghost" size="sm">Back</Button>
            </Link>
            <Link to="/">
              <Button variant="secondary" size="sm">Dashboard</Button>
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}

