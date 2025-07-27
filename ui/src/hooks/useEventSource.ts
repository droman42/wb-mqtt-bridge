import { useEffect, useRef, useState } from "react";
import { runtimeConfig, getSSEUrl } from '@/config/runtime';

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
  addHandler: (handler: (data: any) => void) => void;
  removeHandler: (handler: (data: any) => void) => void;
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
  const handlers = useRef<((data: any) => void)[]>([]);
  
  // 🔧 FIX: Use refs to avoid stale closure issues
  const reconnectAttemptsRef = useRef<number>(0);
  const cancelledRef = useRef<boolean>(false);

  useEffect(() => {
    if (!enabled || !url) {
      return;
    }

    // 🔧 FIX: Reset cancellation flag when effect runs
    cancelledRef.current = false;
    reconnectAttemptsRef.current = 0;
    setReconnectAttempts(0);

    function connect() {
      if (cancelledRef.current) {
        return;
      }

      try {
        // Build full URL with base URL if needed
        // Use Vite proxy for relative URLs  
        const fullUrl = url.startsWith('http') ? url : url;
        
        // For SSE, we need to create the EventSource with specific options
        console.log(`Creating EventSource for ${fullUrl}`);
        const es = new EventSource(fullUrl);
        esRef.current = es;

        es.onopen = () => {
          if (!cancelledRef.current) {
            console.log(`🟢 SSE connection opened for ${fullUrl}`);
            console.log(`🔧 DEBUG: onmessage handler attached:`, typeof es.onmessage);
            setConnected(true);
            setError(null);
            
            // 🔧 FIX: Reset reconnection counters on successful connection
            reconnectAttemptsRef.current = 0;
            setReconnectAttempts(0);
            retryRef.current = retryInterval; // Reset retry interval
          }
        };

        // 🔧 NEW: Single generic message handler for all events
        es.onmessage = (event) => {
          if (!cancelledRef.current) {
            try {
              const eventData = JSON.parse(event.data);
              
              // Extract event type from data payload (new backend format)
              const eventType = eventData.eventType || 'message';
              
              // 🔇 Skip logging for keepalive events to reduce console noise
              if (eventType !== 'keepalive') {
                console.log(`📨 SSE message received on ${url}:`, event);
                console.log(`📋 SSE parsed data:`, eventData);
              }
              
              // Update connection status
              setConnected(true);
              setError(null);
              
              // Reset reconnection counters on successful event
              reconnectAttemptsRef.current = 0;
              setReconnectAttempts(0);
              
              // Update state with event data and type
              setData({ ...eventData, eventType });
              setLastEventType(eventType);

              // Call all registered handlers
              handlers.current.forEach(handler => {
                try {
                  handler(eventData);
                } catch (handlerError) {
                  console.error(`Handler error for ${eventType}:`, handlerError);
                }
              });
              
            } catch (parseError) {
              console.error(`Failed to parse SSE event data:`, parseError, event.data);
            }
          }
        };

        es.onerror = (e) => {
          console.error(`🔴 SSE connection error for ${fullUrl}:`, e);
          console.log(`🔴 SSE readyState: ${es.readyState}, URL: ${es.url}`);
          setError(e);
          setConnected(false);
          es.close();
          
          // 🔧 FIX: Use ref values to avoid stale closure issues
          if (!cancelledRef.current && reconnectAttemptsRef.current < maxRetries) {
            reconnectAttemptsRef.current++;
            setReconnectAttempts(reconnectAttemptsRef.current);
            
            // Exponential back-off with jitter
            const jitter = Math.random() * 1000; // 0-1s jitter
            const delay = Math.min(retryRef.current + jitter, 60_000);
            retryRef.current = Math.min(retryRef.current * 1.5, 30_000);
            
            reconnectTimeoutRef.current = setTimeout(() => {
              if (!cancelledRef.current) connect();
            }, delay);
          }
        };

      } catch (connectError) {
        if (!cancelledRef.current) {
          setError(connectError as Event);
          setConnected(false);
        }
      }
    }

    connect();

    return () => {
      // 🔧 FIX: Set cancellation flag first
      cancelledRef.current = true;
      
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      
      setConnected(false);
    };
  }, [url, enabled, maxRetries, retryInterval, withCredentials]);

  // Add event handler function
  const addHandler = (handler: (data: any) => void) => {
    handlers.current.push(handler);
  };

  // Remove event handler function
  const removeHandler = (handler: (data: any) => void) => {
    handlers.current = handlers.current.filter(h => h !== handler);
  };

  return {
    data,
    error,
    connected,
    reconnectAttempts,
    lastEventType,
    addHandler,
    removeHandler,
  };
}

// Backend data structures based on the new SSE specification
export interface DeviceEventData {
  eventType: string; // Now embedded in data payload by backend
  device_id: string;
  device_name: string;
  message: string;
  timestamp: string;
  // For test events, which have nested data structure
  data?: {
    device_id: string;
    device_name: string;
    message: string;
  };
  // For state_change events, which include device state
  state?: {
    device_id: string;
    device_name: string;
    power?: boolean | string;
    volume?: number;
    mute?: boolean;
    current_app?: string | null;
    input_source?: string | null;
    connected?: boolean;
    ip_address?: string;
    mac_address?: string;
    last_command?: any;
    error?: any;
  };
}

export interface ScenarioEventData {
  eventType: string; // Now embedded in data payload by backend
  scenario_id: string;
  scenario_name?: string;
  message: string;
  timestamp: string;
  progress?: number;
}

export interface SystemEventData {
  eventType: string; // Now embedded in data payload by backend
  message: string;
  timestamp: string;
  level?: 'info' | 'warn' | 'error';
}

// Specialized hooks for different event types - now much simpler
export function useDeviceSSE(enabled: boolean = true) {
  return useEventSource<DeviceEventData>(getSSEUrl(runtimeConfig.sseDevicesPath), { 
    enabled
  });
}

export function useScenarioSSE(enabled: boolean = true) {
  return useEventSource<ScenarioEventData>(getSSEUrl(runtimeConfig.sseScenariosPath), { 
    enabled
  });
}

export function useSystemSSE(enabled: boolean = true) {
  return useEventSource<SystemEventData>(getSSEUrl(runtimeConfig.sseSystemPath), { 
    enabled
  });
} 