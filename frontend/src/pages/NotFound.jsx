/** 404 fallback for unknown routes. */

import { Link } from 'react-router-dom'
import { Button, EmptyState } from '../components/ui'

export default function NotFound() {
  return (
    <EmptyState
      icon="search"
      title="Page not found"
      action={
        <Link to="/">
          <Button variant="primary" icon="dashboard">
            Back to Dashboard
          </Button>
        </Link>
      }
    >
      The page you requested does not exist. Use the sidebar to navigate the analysis pipeline.
    </EmptyState>
  )
}
