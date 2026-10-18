import { create } from "zustand";
import { postQuestion } from "../api/chat";
import type { ChatResponse } from "../types/api";
import { useGraphStore } from "./graphStore";

interface Message {
  question: string;
  response: ChatResponse;
}
interface ChatState {
  messages: Message[];
  loading: boolean;
  error: string;
  lastQuestion: string;
  submitQuestion: (question: string) => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  loading: false,
  error: "",
  lastQuestion: "",
  submitQuestion: async (text) => {
    if (get().loading) return;
    const question = text.trim();
    if (!question || question.length > 4000) {
      set({ error: "Enter a question of 1 to 4000 characters." });
      return;
    }
    set({ loading: true, error: "", lastQuestion: question });
    try {
      const response = await postQuestion(question);
      if (useGraphStore.getState().context === "ask")
        useGraphStore
          .getState()
          .replace(response.graph, response.intent, response.highlighted_paths);
      set((s) => ({ messages: [...s.messages, { question, response }] }));
    } catch (error) {
      set({
        error:
          error instanceof Error
            ? error.message
            : "Request failed. Please retry.",
      });
    } finally {
      set({ loading: false });
    }
  },
}));
