import Link from '@/components/SiteLink.jsx'

export default function InitiativeContact({ showGuideLink = true }) {
  return <section id="contact" className="gp-contact gp-container" aria-labelledby="contact-title">
    <div className="gp-contact-intro"><p className="gp-section-label">Talk to the team at St. Andrew’s</p><h2 id="contact-title">Questions about Golden Plate?</h2><p>For help organizing the initiative, adapting it to your school, or using PLATE, contact Matthew Jaekel at St. Andrew’s College. The school office can also direct your enquiry.</p></div>
    <div className="gp-contact-details">
      <section aria-labelledby="matthew-contact"><h3 id="matthew-contact">Matthew Jaekel</h3><p>Golden Plate enquiries · St. Andrew’s College</p><a className="gp-contact-email" href="mailto:matthew.jaekel@sac.on.ca">matthew.jaekel@sac.on.ca</a><div className="gp-contact-links"><a href="https://ca.linkedin.com/in/mattjaekel" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a><a href="https://thesustainableschool.beehiiv.com/p/sustainable-school-newsletter-let-s-eat-55fa70ca5798ec89" target="_blank" rel="noopener noreferrer">The Sustainable School newsletter ↗</a><a href="https://www.sac.on.ca/news-detail?pk=1541348" target="_blank" rel="noopener noreferrer">Environmental work at SAC ↗</a></div><p className="gp-contact-note">To reach him through the school, call the SAC office below and ask for Matthew Jaekel.</p></section>
      <section aria-labelledby="sac-contact"><h3 id="sac-contact">St. Andrew’s College</h3><p>School office · Aurora, Ontario</p><a className="gp-contact-email" href="mailto:info@sac.on.ca">info@sac.on.ca</a><a className="gp-contact-phone" href="tel:+19057273178">+1 905-727-3178</a><address>15800 Yonge Street<br />Aurora, ON L4G 3H7, Canada</address><p className="gp-contact-note">Office hours: Monday–Friday, 8 a.m.–4 p.m.</p><div className="gp-contact-links"><a href="https://www.sac.on.ca" target="_blank" rel="noopener noreferrer">School website ↗</a><a href="https://www.sac.on.ca/contact-us" target="_blank" rel="noopener noreferrer">Official contact directory ↗</a></div></section>
    </div>
    {showGuideLink && <p className="gp-contact-guide-link">Looking for instructions? <Link to="/getting-started">Read the website getting-started guide →</Link></p>}
  </section>
}
