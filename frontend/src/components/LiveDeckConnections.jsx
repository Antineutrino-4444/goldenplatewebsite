import { deckServices, deckStatus, deckTime, deckUrl } from '@/lib/live-decks.js'
import './LiveDeckConnections.css'

export default function LiveDeckConnections({ connections, providers, onSync, busyId, disabled = false, admin = false, schoolCode = '' }) {
  return <div className="live-deck-connections">
    {admin && <p className="live-deck-services">{Object.entries(deckServices).map(([provider, name]) =>
      <span key={provider}>{name}: {providers[provider] ? 'Configured' : 'Not configured'}</span>)}</p>}
    {connections.length === 0 && <p className="live-deck-empty">No live decks connected for this school.</p>}
    <ul className="live-deck-list" aria-label="Connected presentation services">
      {connections.map(deck => {
        const url = deckUrl(deck.url)
        const syncing = deckStatus(deck) === 'Syncing…'
        const reconnect = deck.status === 'reconnect'
        const manageQuery = new URLSearchParams({ school: schoolCode, theme: deck.theme,
          format: deck.provider === 'google' ? 'google-slides' : 'pptx' })
        return <li key={deck.id} className="live-deck-row">
          <div className="live-deck-details">
            <h4>{deckServices[deck.provider] || 'Presentation'} <span>{deck.theme === 'dark' ? 'Dark' : 'Light'}</span></h4>
            {admin && <p className="live-deck-owner">Connected by {deck.owner_name} <span>@{deck.owner_username}</span></p>}
            <p className="live-deck-state" data-state={deck.status} role="status">{deckStatus(deck)}</p>
            <p className="live-deck-updated">Last synced: {deck.last_synced_at
              ? <time dateTime={deck.last_synced_at}>{deckTime(deck.last_synced_at)}</time> : 'Not synced yet'}</p>
            {deck.message && <p className="live-deck-error">{deck.message}</p>}
            {deck.status === 'retry' && deck.next_check_at && <p className="live-deck-updated">Next retry: <time dateTime={deck.next_check_at}>{deckTime(deck.next_check_at)}</time></p>}
            {admin && reconnect && <p className="live-deck-updated">Ask the connection owner to reconnect their account.</p>}
            {!providers[deck.provider] && <p className="live-deck-error">This service is unavailable on the website.</p>}
          </div>
          <div className="live-deck-actions">
            {url && <a href={url} target="_blank" rel="noopener noreferrer">Open deck</a>}
            {!admin && reconnect ? <a href={'/export?' + manageQuery}>Reconnect</a> :
              <button type="button" disabled={disabled || Boolean(busyId) || syncing || reconnect || !providers[deck.provider]}
                onClick={() => onSync(deck)} aria-label={'Sync ' + deckServices[deck.provider] + ' ' + deck.theme + ' deck' + (admin ? ' for ' + deck.owner_name : '')}>
                {busyId === deck.id ? 'Requesting…' : syncing ? 'Syncing…' : 'Sync now'}
              </button>}
          </div>
        </li>
      })}
    </ul>
  </div>
}
