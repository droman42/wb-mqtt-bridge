import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { persist } from 'zustand/middleware';

interface SettingsState {
  theme: 'light' | 'dark' | 'system';
  language: 'en' | 'ru';
  statePanelOpen: boolean;
  logPanelOpen: boolean;
}

interface SettingsActions {
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  setLanguage: (language: 'en' | 'ru') => void;
  toggleStatePanel: () => void;
  toggleLogPanel: () => void;
  setStatePanelOpen: (open: boolean) => void;
  setLogPanelOpen: (open: boolean) => void;
}

export const useSettingsStore = create<SettingsState & SettingsActions>()(
  persist(
    immer((set) => ({
      theme: 'system',
      language: 'en',
      statePanelOpen: false,
      logPanelOpen: false,

      setTheme: (theme) => set((state) => {
        state.theme = theme;
      }),

      setLanguage: (language) => set((state) => {
        state.language = language;
      }),

      toggleStatePanel: () => set((state) => {
        state.statePanelOpen = !state.statePanelOpen;
      }),

      toggleLogPanel: () => set((state) => {
        state.logPanelOpen = !state.logPanelOpen;
      }),

      setStatePanelOpen: (open) => set((state) => {
        state.statePanelOpen = open;
      }),

      setLogPanelOpen: (open) => set((state) => {
        state.logPanelOpen = open;
      }),
    })),
    {
      name: 'smart-home-settings',
      partialize: (state) => ({
        theme: state.theme,
        language: state.language,
      }),
    }
  )
); 