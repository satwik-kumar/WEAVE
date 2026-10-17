import { useEffect, useState } from 'react';
import { getHealthScore } from '../api/reports';
import { HealthScorePanel } from '../components/health/HealthScorePanel';
import { GapsList } from '../components/health/GapsList';
import type { HealthScore } from '../types/api';

export function HealthPage() {
  const [data, setData] = useState<HealthScore | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealthScore()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 32, color: 'var(--text-secondary)' }}>
        Loading health data...
      </div>
    );
  }
  if (error || !data) {
    return (
      <div style={{ padding: 32, color: 'var(--stale)' }}>
        Failed to load: {error ?? 'Unknown error'}
      </div>
    );
  }

  return (
    <div style={{ padding: 32, maxWidth: 700 }}>
      <HealthScorePanel data={data} />
      <div style={{ marginTop: 24 }}>
        <GapsList gaps={data.gaps} />
      </div>
    </div>
  );
}
