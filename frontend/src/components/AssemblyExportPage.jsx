import { useEffect } from 'react'
import { useTheme } from 'next-themes'
import { PublicFooter } from '@/components/LandingPage.jsx'
import PresentationDownloads from '@/components/PresentationDownloads.jsx'
import './SchoolResourcesPage.css'

export default function AssemblyExportPage() {
  const { resolvedTheme } = useTheme()
  useEffect(() => { document.title = 'Export assembly slides · Golden Plate' }, [])

  return <div className="golden-public gp-school-resources gp-assembly-export">
    <main id="main-content" tabIndex={-1}>
      <PresentationDownloads theme={resolvedTheme === 'dark' ? 'dark' : 'light'} />
    </main>
    <PublicFooter />
  </div>
}
