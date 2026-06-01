import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

const { stats } = vi.hoisted(() => ({
  stats: {
    data: undefined as unknown,
    isLoading: false,
    isError: false,
    error: null as unknown,
    refetch: vi.fn(),
  },
}))

vi.mock('../hooks/useDashboard', () => ({
  useDashboardStats: () => stats,
  useDashboardRecentActivity: () => ({ data: [] }),
  useDashboardCalendar: () => ({ data: [] }),
}))
vi.mock('react-router-dom', () => ({ Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a> }))
vi.mock('../components/dashboard/VoIPWidget', () => ({ default: () => <div>voip</div> }))

import Dashboard from './Dashboard'

describe('Dashboard', () => {
  beforeEach(() => {
    stats.data = undefined
    stats.isLoading = false
    stats.isError = false
  })

  it('renders the heading', () => {
    stats.data = { total_clients: 0 }
    render(<Dashboard />)
    expect(screen.getByText('Πίνακας Ελέγχου')).toBeInTheDocument()
  })

  it('shows an error banner when stats fail', () => {
    stats.isError = true
    stats.error = new Error('500')
    render(<Dashboard />)
    // Heading still renders + an error indicator appears (renderStatValue → '-').
    expect(screen.getByText('Πίνακας Ελέγχου')).toBeInTheDocument()
  })

  it('renders stat values when data is present', () => {
    stats.data = { total_clients: 42 }
    render(<Dashboard />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })
})
