import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

const { reports } = vi.hoisted(() => ({
  reports: {
    data: undefined as unknown,
    isLoading: false,
    isError: false,
    error: null as unknown,
    refetch: vi.fn(),
  },
}))

vi.mock('../hooks/useReports', () => ({
  useReportsStats: () => reports,
  useReportExport: () => ({
    isExporting: false,
    exportType: null,
    exportClients: vi.fn(),
    exportObligations: vi.fn(),
    exportMonthlyPdf: vi.fn(),
  }),
}))
// recharts renders heavy SVG; stub to keep the test light.
vi.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null, XAxis: () => null, YAxis: () => null,
  CartesianGrid: () => null, Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

import Reports from './Reports'

describe('Reports', () => {
  beforeEach(() => {
    reports.data = undefined
    reports.isLoading = false
    reports.isError = false
  })

  it('renders the heading', () => {
    render(<Reports />)
    expect(screen.getByText('Αναφορές')).toBeInTheDocument()
  })

  it('shows an error banner when stats fail', () => {
    reports.isError = true
    reports.error = new Error('boom')
    render(<Reports />)
    expect(screen.getByText(/Σφάλμα φόρτωσης δεδομένων/)).toBeInTheDocument()
  })

  it('shows empty chart state when no data', () => {
    reports.data = { obligations_by_type: [], monthly_activity: [] }
    render(<Reports />)
    expect(screen.getAllByText('Δεν υπάρχουν δεδομένα').length).toBeGreaterThan(0)
  })
})
