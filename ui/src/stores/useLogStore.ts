import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { LogEntry } from '../types/Prompt';
import { runtimeConfig } from '../config/runtime';

interface LogState {
  entries: LogEntry[];
}

interface LogActions {
  addLog: (entry: Omit<LogEntry, 'id' | 'timestamp'>) => void;
  clearLogs: () => void;
}

export const useLogStore = create<LogState & LogActions>()(
  immer((set) => ({
    entries: [],

    addLog: (entry) => set((state) => {
      const newEntry: LogEntry = {
        ...entry,
        id: Math.random().toString(36).substr(2, 9),
        timestamp: Date.now(),
      };
      
      state.entries.unshift(newEntry);
      
      // Keep only the most recent entries
      if (state.entries.length > runtimeConfig.maxLogEntries) {
        state.entries = state.entries.slice(0, runtimeConfig.maxLogEntries);
      }
    }),

    clearLogs: () => set((state) => {
      state.entries = [];
    }),
  }))
); 