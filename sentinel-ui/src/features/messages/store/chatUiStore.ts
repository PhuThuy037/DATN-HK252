import { create } from "zustand";

type ChatUiState = {
  selectedMessageId: string | null;
  setSelectedMessageId: (messageId: string | null) => void;
  clearSelectedMessageId: () => void;
};

export const useChatUiStore = create<ChatUiState>((set) => ({
  selectedMessageId: null,
  setSelectedMessageId: (messageId) => set({ selectedMessageId: messageId }),
  clearSelectedMessageId: () => set({ selectedMessageId: null }),
}));
