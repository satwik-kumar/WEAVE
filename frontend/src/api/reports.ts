import { request } from "./client";
import type {
  HealthReport,
  OnboardingBrief,
  DecisionReport,
} from "../types/api";

export const getHealthReport = () =>
  request<HealthReport>("/reports/health-score");
export const getOnboardingBrief = (service: string) =>
  request<OnboardingBrief>(
    `/reports/onboarding/${encodeURIComponent(service)}`,
  );
export const getDecisions = (service: string) =>
  request<DecisionReport>(`/services/${encodeURIComponent(service)}/decisions`);
