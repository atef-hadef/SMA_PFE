import StatusBadge, { type StatusType } from './StatusBadge'

type TableRow = {
  id: string
  process: string
  owner: string
  status: StatusType
}

type DataTableProps = {
  title: string
  rows: TableRow[]
  emptyMessage?: string
}

function DataTable({
  title,
  rows,
  emptyMessage = 'Aucun événement récent.',
}: DataTableProps) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl shadow-slate-950/30">
      <div className="flex items-center justify-between gap-4 border-b border-slate-800 px-5 py-4">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="mt-1 text-sm text-slate-400">Derniers événements métier enregistrés</p>
        </div>
        <span className="rounded-md border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs font-semibold text-slate-300">
          {rows.length} événements
        </span>
      </div>
      <div className="overflow-x-auto">
        {rows.length === 0 ? (
          <p className="p-5 text-sm text-slate-400">{emptyMessage}</p>
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-950/70 text-xs uppercase tracking-[0.14em] text-slate-400">
              <tr>
                <th className="px-5 py-3 font-semibold">Processus</th>
                <th className="px-5 py-3 font-semibold">Responsable</th>
                <th className="px-5 py-3 font-semibold">Statut</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {rows.map((row) => (
                <tr key={row.id} className="transition hover:bg-slate-900/60">
                  <td className="px-5 py-4 font-medium text-white">{row.process}</td>
                  <td className="px-5 py-4 text-slate-300">{row.owner}</td>
                  <td className="px-5 py-4">
                    <StatusBadge label={row.status} status={row.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

export type { TableRow }
export default DataTable
