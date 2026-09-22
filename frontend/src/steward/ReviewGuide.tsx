import { Pill, ConfidencePill } from '../components'

export function ReviewGuide() {
  return (
    <div style={{
      flex: 1, overflow: 'auto', background: 'var(--db-oat-light)', padding: '28px 32px 48px',
    }}>
      <div style={{ maxWidth: 760 }}>
        <div style={{
          fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
          letterSpacing: '0.08em', fontWeight: 500, marginBottom: 6,
        }}>Reference</div>
        <h1 style={{
          fontSize: 26, fontWeight: 500, letterSpacing: '-0.018em',
          color: 'var(--db-navy-800)', margin: 0,
        }}>Review guide</h1>

        <div style={{
          background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 10,
          padding: 24, marginTop: 20,
        }}>
          <h3 style={{ fontSize: 16, margin: '0 0 10px', fontWeight: 500, color: 'var(--db-navy-800)' }}>
            What you're reviewing
          </h3>
          <p style={{ fontSize: 13.5, color: 'var(--db-navy-800)', lineHeight: 1.6, margin: 0 }}>
            Unity Catalog's data classifier scans the contents of tables you own and proposes semantic tags
            (<code style={{ fontFamily: 'var(--font-mono)', background: 'var(--db-oat-light)', padding: '0 4px', borderRadius: 3 }}>class.name</code>
            , <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--db-oat-light)', padding: '0 4px', borderRadius: 3 }}>class.email_address</code>
            , etc.) on the columns where it found matching content. You decide which proposals to approve before they are applied to the catalog.
          </p>

          <h3 style={{
            fontSize: 16, margin: '20px 0 10px', fontWeight: 500, color: 'var(--db-navy-800)',
          }}>Decision guide</h3>
          <div style={{
            display: 'grid', gridTemplateColumns: '120px 1fr', gap: '10px 18px',
            fontSize: 13, lineHeight: 1.6, color: 'var(--db-navy-800)',
          }}>
            <div><Pill bg="#9ED6C4" color="#095A35" dot>Approve</Pill></div>
            <div>The proposed tag describes this column accurately. The samples match the category.</div>
            <div><Pill bg="#BAE1FC" color="#04355D" dot>Modify</Pill></div>
            <div>
              The column contains sensitive data but the proposed category is wrong
              (e.g. it's <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--db-oat-light)', padding: '0 4px', borderRadius: 3 }}>class.location</code>
              , not <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--db-oat-light)', padding: '0 4px', borderRadius: 3 }}>class.address</code>). Pick the right tag.
            </div>
            <div><Pill bg="#FABFBA" color="#801C17" dot>Reject</Pill></div>
            <div>False positive. The classifier matched on incidental content (e.g. a name mentioned in free-text once).</div>
          </div>

          <h3 style={{
            fontSize: 16, margin: '20px 0 10px', fontWeight: 500, color: 'var(--db-navy-800)',
          }}>Confidence</h3>
          <p style={{ fontSize: 13.5, color: 'var(--db-navy-800)', lineHeight: 1.6, margin: 0 }}>
            <ConfidencePill level="HIGH" /> means a high match rate against the classifier's pattern dictionary.{' '}
            <ConfidencePill level="LOW" /> means a sparse match — usually free-text fields with occasional matches. Review LOW proposals carefully.
          </p>
        </div>
      </div>
    </div>
  )
}
