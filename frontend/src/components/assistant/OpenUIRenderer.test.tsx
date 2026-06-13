import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import OpenUIRenderer from './OpenUIRenderer'
import { assistantActionRequiresConfirmation } from './assistantActions'
import type { SuggestedAction } from '../../services/assistantService'

const validDashboard = `
root = AssistantDashboard("Résumé CRM", "Pipeline CRM : 2 leads haute priorité.", [
  DashboardSection("Indicateurs", null, [
    KpiGrid([KpiCard("Leads haute priorité", "2", "Calculé depuis PostgreSQL", null, null, "info")])
  ])
])
`

describe('OpenUIRenderer', () => {
  it('renders valid OpenUI content', async () => {
    render(<OpenUIRenderer content={validDashboard} />)

    expect(await screen.findByText('Résumé CRM')).toBeInTheDocument()
    expect(screen.getByText('Leads haute priorité')).toBeInTheDocument()
  })

  it('calls fallback for empty content', async () => {
    const onInvalidContent = vi.fn()

    render(<OpenUIRenderer content="   " onInvalidContent={onInvalidContent} />)

    await waitFor(() => expect(onInvalidContent).toHaveBeenCalled())
  })

  it('calls fallback for invalid OpenUI content', async () => {
    const onInvalidContent = vi.fn()

    render(<OpenUIRenderer content={'root = UnknownCard("x")'} onInvalidContent={onInvalidContent} />)

    await waitFor(() => expect(onInvalidContent).toHaveBeenCalled())
  })

  it('emits suggested actions', async () => {
    const onAction = vi.fn()
    const content = `
root = AssistantDashboard("Actions", "Choisissez une suite.", [
  DashboardSection("Suite", null, [
    SuggestedActions("Actions suggérées", [{label: "Ouvrir le CRM", actionType: "navigate", route: "/crm-leads", requiresConfirmation: false}])
  ])
])
`

    render(<OpenUIRenderer content={content} onAction={onAction} />)

    fireEvent.click(await screen.findByRole('button', { name: /Ouvrir le CRM/i }))
    expect(onAction).toHaveBeenCalledWith(
      expect.objectContaining({
        label: 'Ouvrir le CRM',
        action_type: 'navigate',
      }),
    )
  })

  it('renders empty states for empty business data', async () => {
    const content = `
root = AssistantDashboard("Données", "Aucune ligne disponible.", [
  DashboardSection("Table", null, [
    SmartDataTable("Hot leads", "Liste validée", [{key: "Nom", label: "Nom", align: "left"}], [], "Aucun hot lead.")
  ])
])
`
    render(<OpenUIRenderer content={content} />)

    expect(await screen.findByText('Aucun hot lead.')).toBeInTheDocument()
  })

  it('renders modern CRM priority components', async () => {
    const content = `
root = AssistantDashboard("Hot leads", "Un lead nécessite une action.", [
  DashboardSection("Réponse directe", null, [
    SingleMetricCard("Leads haute priorité", 1, "Calculé depuis PostgreSQL", "warning", null)
  ]),
  DashboardSection("Priorités", null, [
    PriorityLeadTable("Leads prioritaires", "Liste validée", [{name: "Atef", company: "Tactic", score: 98, status: "hot"}], "Aucun lead prioritaire.")
  ]),
  DashboardSection("Fiabilité", null, [
    InsufficientDataState("Données limitées", "Le volume CRM disponible est faible.", "Rester factuel.")
  ])
])
`
    render(<OpenUIRenderer content={content} />)

    expect(await screen.findByText('Leads haute priorité')).toBeInTheDocument()
    expect(screen.getByText('Atef')).toBeInTheDocument()
    expect(screen.getByText('Données limitées')).toBeInTheDocument()
  })
})

describe('assistantActionRequiresConfirmation', () => {
  it('does not require confirmation for navigation', () => {
    const action: SuggestedAction = { label: 'Ouvrir', action_type: 'navigate', payload: { route: '/crm-leads' } }

    expect(assistantActionRequiresConfirmation(action)).toBe(false)
  })

  it('requires confirmation for mutations', () => {
    const action: SuggestedAction = { label: 'Envoyer', action_type: 'send_approved_email', payload: {} }

    expect(assistantActionRequiresConfirmation(action)).toBe(true)
  })
})
