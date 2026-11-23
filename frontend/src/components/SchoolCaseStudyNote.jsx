import Link from '@/components/SiteLink.jsx'

// The supplied PDF has no printed publication date. Its ModDate identifies this edition.
export default function SchoolCaseStudyNote() {
  return <p className="gp-case-study-note">
    Second Harvest case study, PDF last updated <time dateTime="2026-05-29">May 29, 2026</time>.
    {' '}Its figures and instructions are outdated. See <Link to="/how-it-works">how Golden Plate works today</Link> for current information.
  </p>
}
