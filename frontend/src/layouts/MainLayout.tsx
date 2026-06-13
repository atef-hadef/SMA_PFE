import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopHeader from './TopHeader'

type MainLayoutProps = {
  children: ReactNode
}

function MainLayout({ children }: MainLayoutProps) {
  const { pathname } = useLocation()
  // Full-bleed, fixed-height chat surface for the assistant (ChatGPT/Claude style):
  // no header, no padding, no centered max-width wrapper.
  const isFullBleed = pathname === '/assistant'

  return (
    <div
      className={`${isFullBleed ? 'h-screen overflow-hidden' : 'min-h-screen'} bg-linear-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100`}
    >
      <div className={`flex ${isFullBleed ? 'h-screen' : 'min-h-screen'}`}>
        <Sidebar />

        <div className="flex min-w-0 flex-1 flex-col">
          <TopHeader />
          {isFullBleed ? (
            <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
          ) : (
            <main className="flex-1 px-4 py-6 sm:px-6 md:px-8 md:py-8">
              <div className="mx-auto max-w-7xl">{children}</div>
            </main>
          )}
        </div>
      </div>
    </div>
  )
}

export default MainLayout
