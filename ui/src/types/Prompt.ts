export interface PromptPage {
  id: string;
  title: { en: string; ru: string };

  menu?: {
    up: string; 
    down: string; 
    left: string; 
    right: string;
    ok: string;
    aux1: string; 
    aux2: string; 
    aux3: string; 
    aux4: string;
  };

  sliders?: Array<{
    id: string;
    min: number; 
    max: number; 
    step?: number;
    icon?: string;           // Heroicon or "lucide:<name>"
    ticks?: number[];
    transport?: 'api'|'mqtt';
    payload?: Record<string, unknown>;
  }>;

  pointer?: {
    mode: 'relative'|'absolute';
    sensitivity?: number;
    transport?: 'api'|'mqtt';
    hintIcon?: string|false;
  };

  buttons?: Array<{
    id: string;
    icon?: string;
    label?: { en: string; ru: string };
    transport?: 'api'|'mqtt';
    payload?: Record<string, unknown>;
    promptForInput?: { label: { en: string; ru: string }; paramKey: string };
    holdable?: boolean;
  }>;

  hideStatePanel?: boolean;
}

export interface LogEntry {
  id: string;
  timestamp: number;
  level: 'info' | 'warn' | 'error';
  message: string;
  details?: Record<string, unknown>;
}

export interface BaseDeviceState {
  id: string;
  online: boolean;
  lastSeen?: number;
  [key: string]: unknown;
} 