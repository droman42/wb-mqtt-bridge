import { useEffect, useRef, useState } from "react";

export interface SSEOptions {
  withCredentials?: boolean;
  headers?: Record<string, string>;
  retryInterval?: number;
  maxRetries?: number;
  enabled?: boolean;
}

export interface SSEState<T> {
  data: T | null;
  error: Event | null;
  connected: boolean;
  reconnectAttempts: number;
  lastEventType?: string;
}

export function useEventSource<T = any>(
  url: string,
  {
    withCredentials = false,
    headers = {},
    retryInterval = 5_000,
    maxRetries = 10,
    enabled = true,
  }: SSEOptions = {}
): SSEState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Event | null>(null);
  const [connected, setConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [lastEventType, setLastEventType] = useState<string | undefined>();
  
  const esRef = useRef<EventSource | null>(null);
  const retryRef = useRef<number>(retryInterval);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!enabled || !url) {
      console.log(`[SSE] Hook disabled or no URL: enabled=${enabled}, url=${url}`);
      return;
    }

    let cancelled = false;

    function connect() {
      if (cancelled) return;

      try {
        // Build full URL with base URL if needed
        const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const fullUrl = url.startsWith('http') ? url : `${baseUrl}${url}`;
        
        console.log(`[SSE] Attempting to connect to: ${fullUrl}`);
        
        // For custom headers, we'd need a polyfill, but for now use basic EventSource
        const es = new EventSource(fullUrl, { withCredentials });
        esRef.current = es;

        es.onopen = () => {
          if (!cancelled) {
            console.log(`[SSE] Connected to ${fullUrl}`);
            setConnected(true);
            setError(null);
            setReconnectAttempts(0);
            retryRef.current = retryInterval; // Reset retry interval
          }
        };

        es.onmessage = (e) => {
          if (!cancelled) {
            console.log(`[SSE] Received default message from ${fullUrl}:`, e.data);
            try {
              const parsedData = JSON.parse(e.data);
              setData(parsedData);
              setLastEventType('message');
            } catch (parseError) {
              console.warn('Failed to parse SSE data as JSON:', e.data);
              setData(e.data as T);
              setLastEventType('message');
            }
          }
        };

        // Handle all possible backend event types
        const deviceEventTypes = [
          'device_setup', 'connection_attempt', 'connection_success', 'connection_failed',
          'device_action', 'device_state_change', 'device_progress'
        ];
        
        const scenarioEventTypes = [
          'scenario_start', 'scenario_progress', 'scenario_complete', 'scenario_error'
        ];
        
        const systemEventTypes = [
          'system_info', 'system_warning', 'system_error', 'config_reload', 
          'device_discovery', 'keepalive', 'connected'
        ];
        
        const allEventTypes = [...deviceEventTypes, ...scenarioEventTypes, ...systemEventTypes];
        
        allEventTypes.forEach(eventType => {
          es.addEventListener(eventType, (event) => {
            if (!cancelled) {
              console.log(`[SSE] Received ${eventType} event from ${fullUrl}:`, (event as MessageEvent).data);
              try {
                const parsedData = JSON.parse((event as MessageEvent).data);
                // Add the event type to the data for easier handling
                const dataWithEventType = { ...parsedData, eventType };
                setData(dataWithEventType);
                setLastEventType(eventType);
              } catch (parseError) {
                console.warn(`Failed to parse SSE data for event ${eventType}:`, (event as MessageEvent).data);
                const dataWithEventType = { data: (event as MessageEvent).data, eventType } as T;
                setData(dataWithEventType);
                setLastEventType(eventType);
              }
            }
          });
        });

        es.onerror = (e) => {
          console.error(`[SSE] Connection error for ${fullUrl}:`, e);
          setError(e);
          setConnected(false);
          es.close();
          
          // Only retry if we haven't exceeded max retries and not cancelled
          if (!cancelled && reconnectAttempts < maxRetries) {
            setReconnectAttempts(prev => prev + 1);
            
            // Exponential back-off with jitter
            const jitter = Math.random() * 1000; // 0-1s jitter
            const delay = Math.min(retryRef.current + jitter, 60_000);
            retryRef.current = Math.min(retryRef.current * 1.5, 30_000);
            
            console.log(`[SSE] Retrying connection to ${fullUrl} in ${Math.round(delay)}ms (attempt ${reconnectAttempts + 1}/${maxRetries})`);
            
            reconnectTimeoutRef.current = setTimeout(() => {
              if (!cancelled) connect();
            }, delay);
          } else {
            console.error(`[SSE] Max retries reached for ${fullUrl} or connection cancelled`);
          }
        };

      } catch (connectError) {
        console.error(`[SSE] Failed to create EventSource for ${url}:`, connectError);
        if (!cancelled) {
          setError(connectError as Event);
          setConnected(false);
        }
      }
    }

    console.log(`[SSE] Initializing connection for ${url}`);
    connect();

    return () => {
      console.log(`[SSE] Cleaning up connection for ${url}`);
      cancelled = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      esRef.current?.close();
      setConnected(false);
    };
  }, [url, withCredentials, enabled, retryInterval, maxRetries]);

  return { data, error, connected, reconnectAttempts, lastEventType };
}

// Backend data structures based on the SSE specification
export interface DeviceEventData {
  device_id: string;
  device_name: string;
  message: string;
  timestamp: string;
  eventType?: string; // Added by frontend
}

export interface ScenarioEventData {
  scenario_id: string;
  scenario_name?: string;
  message: string;
  timestamp: string;
  progress?: number;
  eventType?: string; // Added by frontend
}

export interface SystemEventData {
  message: string;
  timestamp: string;
  level?: 'info' | 'warn' | 'error';
  eventType?: string; // Added by frontend
}

// Specialized hooks for different event types
export function useDeviceSSE(enabled: boolean = true) {
  return useEventSource<DeviceEventData>('/events/devices', { enabled });
}

export function useScenarioSSE(enabled: boolean = true) {
  return useEventSource<ScenarioEventData>('/events/scenarios', { enabled });
}

export function useSystemSSE(enabled: boolean = true) {
  return useEventSource<SystemEventData>('/events/system', { enabled });
} 