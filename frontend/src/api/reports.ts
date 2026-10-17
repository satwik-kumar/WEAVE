import { apiGet } from './client';
import type { HealthScore } from '../types/api';

export const getHealthScore = () =>
  apiGet<HealthScore>('/api/v1/reports/health-score');

export const getKnowledgeGaps = () =>
  apiGet<{ gaps: import('../types/api').KnowledgeGap[] }>(
    '/api/v1/reports/knowledge-gaps'
  );

export const getOnboardingBrief = (serviceId: string) =>
  apiGet<Record<string, unknown>>(
    `/api/v1/reports/onboarding?service_id=${encodeURIComponent(serviceId)}`
  );

export const getDecisionsForTimeline = async (serviceId: string) => {
  const brief = await getOnboardingBrief(serviceId);
  return (brief.key_decisions ?? []) as Array<Record<string, unknown>>;
};
