export interface LogEntry {
  id: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  timestamp: number;
  category?: string;
  deviceId?: string;
  source?: string;
  details?: any;
} 