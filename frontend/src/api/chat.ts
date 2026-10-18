import type { ChatResponse } from "../types/api";
import { request } from "./client";

export const postQuestion = (question: string) =>
  request<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
