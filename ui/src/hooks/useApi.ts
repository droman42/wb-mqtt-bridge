import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import type { components } from '../types/openapi.gen';
import type {
  DeviceAction,
  MQTTMessage,
  SwitchScenarioRequest,
  ActionRequest,
  SystemInfo,
  SystemConfigResponse,
  ReloadResponse,
  RoomDefinitionResponse,
  ScenarioDefinition,
  ScenarioState,
  ScenarioResponse,
  CommandResponse,
  DeviceState,
  MQTTPublishResponse,
  PersistedStatesResponse,
  ReconcilePreviewResponse,
  ForceReconcileResponse,
} from '../types/api';
import { BaseDeviceState } from '../types/BaseDeviceState';
import { collectUiEvidence, recordApiCall } from '../lib/reportEvidence';

// Create axios instance with base configuration
// Use relative URLs when VITE_API_BASE_URL is empty (for nginx proxy)
const getBaseURL = () => {
  const envURL = import.meta.env.VITE_API_BASE_URL;
  if (envURL === undefined || envURL === null) {
    return 'http://localhost:8000'; // Development fallback
  }
  return envURL === '' ? '/api' : envURL; // Empty string means use nginx proxy
};

const api = axios.create({
  baseURL: getBaseURL(),
  // No timeout - let backend manage operation-specific timeouts
});

// Problem-report API evidence ring (B-4): method/path/status/duration per call,
// error bodies on failures — dumped only into a filed report's ui_evidence.
api.interceptors.request.use((config) => {
  (config as { _evidenceStart?: number })._evidenceStart = Date.now();
  return config;
});
api.interceptors.response.use(
  (response) => {
    const start = (response.config as { _evidenceStart?: number })._evidenceStart ?? Date.now();
    recordApiCall({
      ts: Date.now(),
      method: (response.config.method ?? '?').toUpperCase(),
      path: response.config.url ?? '?',
      status: response.status,
      durationMs: Date.now() - start,
    });
    return response;
  },
  (error: unknown) => {
    const err = error as {
      config?: { method?: string; url?: string; _evidenceStart?: number };
      response?: { status?: number; data?: unknown };
      message?: string;
    };
    const start = err.config?._evidenceStart ?? Date.now();
    recordApiCall({
      ts: Date.now(),
      method: (err.config?.method ?? '?').toUpperCase(),
      path: err.config?.url ?? '?',
      status: err.response?.status ?? null,
      durationMs: Date.now() - start,
      error: err.response?.data ? JSON.stringify(err.response.data).slice(0, 300) : err.message,
    });
    return Promise.reject(error);
  }
);

// Problem reporting (problem_reports_bridge.md B-8/B-12): the navbar bug button's
// filing call. Browser evidence is collected at send time, server assembles the rest.
export type ReportRequest = components['schemas']['ReportRequest'];
export type ReportResponse = components['schemas']['ReportResponse'];
export const fileProblemReport = (freeText: string, entityId: string | null) =>
  api.post<ReportResponse>('/reports', {
    free_text: freeText,
    context: { route: window.location.pathname, entity_id: entityId },
    ui_evidence: collectUiEvidence(),
  } satisfies ReportRequest).then(res => res.data);

// System hooks
export const useSystemInfo = () => {
  return useQuery({
    queryKey: ['system', 'info'],
    queryFn: () => api.get<SystemInfo>('/system').then(res => res.data),
  });
};

export const useSystemConfig = () => {
  return useQuery({
    queryKey: ['system', 'config'],
    queryFn: () => api.get<SystemConfigResponse>('/config/system').then(res => res.data),
  });
};

export const useReloadSystem = () => {
  return useMutation({
    mutationFn: () => api.post<ReloadResponse>('/reload').then(res => res.data),
  });
};

// Device hooks
export const useDeviceConfig = (deviceId: string) => {
  return useQuery({
    queryKey: ['devices', deviceId, 'config'],
    queryFn: () => api.get<any>(`/config/device/${deviceId}`).then(res => res.data),
    enabled: !!deviceId,
  });
};

export const useAllDeviceConfigs = () => {
  return useQuery({
    queryKey: ['devices', 'configs'],
    queryFn: () => api.get<any>('/config/devices').then(res => res.data),
  });
};

export const useDeviceState = (deviceId: string) => {
  return useQuery({
    queryKey: ['devices', deviceId, 'state'],
    queryFn: () => api.get<BaseDeviceState>(`/devices/${deviceId}/state`).then(res => res.data),
    enabled: !!deviceId,
    // No more aggressive polling - only fetch on mount and after actions
  });
};

// Layer 3 (Step 2): the backend-served layout manifest (page STRUCTURE). Structural,
// not live state — fetch once and keep (live state still flows via /state + SSE).
export type LayoutManifest = components['schemas']['LayoutManifest'];
export const useDeviceLayout = (deviceId: string) => {
  return useQuery({
    queryKey: ['devices', deviceId, 'layout'],
    queryFn: () => api.get<LayoutManifest>(`/devices/${deviceId}/layout`).then(res => res.data),
    enabled: !!deviceId,
    staleTime: Infinity,
  });
};

// Layer 3 (Step 3): the scenario composite-remote manifest (entityKind="scenario").
export const useScenarioLayout = (scenarioId: string) => {
  return useQuery({
    queryKey: ['scenario', scenarioId, 'layout'],
    queryFn: () => api.get<LayoutManifest>(`/scenario/${scenarioId}/layout`).then(res => res.data),
    enabled: !!scenarioId,
    staleTime: Infinity,
  });
};

export const useDevicePersistedState = (deviceId: string) => {
  return useQuery({
    queryKey: ['devices', deviceId, 'persisted'],
    queryFn: () => api.get<DeviceState>(`/devices/${deviceId}/persisted_state`).then(res => res.data),
    enabled: !!deviceId,
  });
};

export const useAllPersistedStates = () => {
  return useQuery({
    queryKey: ['devices', 'persisted'],
    queryFn: () => api.get<PersistedStatesResponse>('/devices/persisted_states').then(res => res.data),
  });
};

export const useExecuteDeviceAction = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, action }: { deviceId: string; action: DeviceAction }) =>
      api.post<CommandResponse>(`/devices/${deviceId}/action`, action).then(res => res.data),
    onSuccess: (response, { deviceId, action }) => {
      // If the response includes updated state, immediately update the cache
      if (response.state) {
        // Update the device state cache with the response data
        queryClient.setQueryData(['devices', deviceId, 'state'], response.state);
        
        // Also add last_command info to the state if not already present
        if (!response.state.last_command) {
          const updatedState = {
            ...response.state,
            last_command: {
              action: action.action,
              source: 'frontend',
              timestamp: new Date().toISOString(),
              params: action.params || null,
            },
          };
          queryClient.setQueryData(['devices', deviceId, 'state'], updatedState);
        }
      } else {
        // Fallback: invalidate to trigger refetch if no state in response
        void queryClient.invalidateQueries({ queryKey: ['devices', deviceId, 'state'] });
      }
    },
  });
};

// Single-poll methods for explicit state checking
export const usePollDeviceState = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (deviceId: string) => 
      api.get<BaseDeviceState>(`/devices/${deviceId}/state`).then(res => res.data),
    onSuccess: (data, deviceId) => {
      // Update the query cache with fresh data
      queryClient.setQueryData(['devices', deviceId, 'state'], data);
    },
  });
};

// §P3.7 #17 — catalog: flat capability projection of the whole house (rooms + devices +
// per-capability fields incl. value tables). The HvacPanel reads value labels from here.
export type CatalogResponse = components['schemas']['CatalogResponse'];
export const useSystemCatalog = () => {
  return useQuery({
    queryKey: ['system', 'catalog'],
    queryFn: () => api.get<CatalogResponse>('/system/catalog').then(res => res.data),
    staleTime: Infinity,  // version-hashed; we refetch on /reload notification, not on a timer.
  });
};

// §P3.7 #15 — canonical action endpoint. Voice + UI both POST canonical
// (capability, action, params) tuples; bridge resolves to native via the capability
// map and translates value-table entries (§P3.7 #26) before publishing on the bus.
export type CanonicalActionRequest = components['schemas']['CanonicalActionRequest'];
export type CanonicalActionResponse = components['schemas']['CanonicalActionResponse'];
export const useExecuteCanonicalAction = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, request }: { deviceId: string; request: CanonicalActionRequest }) =>
      api.post<CanonicalActionResponse>(`/devices/${deviceId}/canonical`, request).then(res => res.data),
    onSuccess: (response, { deviceId, request }) => {
      // The bridge waits for the value-topic echo (up to ~500ms) and returns post-state.
      // Merge into cache so live state reflects immediately; otherwise invalidate.
      if (response.state) {
        queryClient.setQueryData(['devices', deviceId, 'state'], response.state);
      } else {
        void queryClient.invalidateQueries({ queryKey: ['devices', deviceId, 'state'] });
      }
      // A scenario lifecycle dispatch (scenario.set / scenario.off on the room's
      // Scenario Manager entity) changes which scenario is active — refresh the
      // scenario-state queries so an open scenario page goes live without waiting
      // for the SSE round-trip. (Rack finding 2026-07-07: the page stayed stale
      // until reload — canonical became the primary path in UI-9 but only the
      // legacy /scenario/switch mutation invalidated these keys.)
      if (request.capability === 'scenario') {
        void queryClient.invalidateQueries({ queryKey: ['scenario', 'state'] });
        void queryClient.invalidateQueries({ queryKey: ['scenarios', 'state'] });
        void queryClient.invalidateQueries({ queryKey: ['devices'] });
      }
    },
  });
};

// SCN-7 — option enumeration is a READ. Dropdown population (available inputs / apps)
// fetches GET /devices/{id}/options/{kind} instead of POSTing a get_available_* action;
// the response keeps the driver's result envelope ({success, data: [...]}).
export const fetchDeviceOptions = (deviceId: string, kind: 'inputs' | 'apps') =>
  api
    .get<{ success?: boolean; data?: unknown; error?: string }>(`/devices/${deviceId}/options/${kind}`)
    .then(res => res.data);

// Room hooks
export const useRooms = () => {
  return useQuery({
    queryKey: ['rooms'],
    queryFn: () => api.get<RoomDefinitionResponse[]>('/room/list').then(res => res.data),
  });
};

export const useRoom = (roomId: string) => {
  return useQuery({
    queryKey: ['rooms', roomId],
    queryFn: () => api.get<RoomDefinitionResponse>(`/room/${roomId}`).then(res => res.data),
    enabled: !!roomId,
  });
};

// Scenario hooks
export const useScenarios = (roomId?: string) => {
  return useQuery({
    queryKey: ['scenarios', roomId],
    queryFn: () => {
      const params = roomId ? { room: roomId } : {};
      return api.get<ScenarioDefinition[]>('/scenario/definition', { params }).then(res => res.data);
    },
  });
};

export const useScenarioDefinition = (scenarioId: string) => {
  return useQuery({
    queryKey: ['scenarios', 'definition', scenarioId],
    queryFn: () => api.get<ScenarioDefinition>(`/scenario/definition/${scenarioId}`).then(res => res.data),
    enabled: !!scenarioId,
  });
};

export const useScenarioState = () => {
  return useQuery({
    queryKey: ['scenario', 'state'],
    queryFn: () => api.get<ScenarioState>('/scenario/state').then(res => res.data),
  });
};

// New hook for specific scenario state
export const useSpecificScenarioState = (scenarioId: string) => {
  return useQuery({
    queryKey: queryKeys.scenarios.specificState(scenarioId),
    queryFn: () => api.get<ScenarioState>(`/scenario/${scenarioId}/state`).then(res => res.data),
    enabled: !!scenarioId,
  });
};

export const useSwitchScenario = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: SwitchScenarioRequest) =>
      api.post<ScenarioResponse>('/scenario/switch', request).then(res => res.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scenario', 'state'] });
      void queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });
};

export const useExecuteRoleAction = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: ActionRequest) =>
      api.post<ScenarioResponse>('/scenario/role_action', request).then(res => res.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scenario', 'state'] });
      void queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });
};

// Scenario start/shutdown hooks
export const useStartScenario = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scenarioId: string) =>
      api.post<ScenarioResponse>('/scenario/start', { id: scenarioId }).then(res => res.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scenario', 'state'] });
      void queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });
};

export const useShutdownScenario = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ scenarioId, graceful = true }: { scenarioId: string; graceful?: boolean }) =>
      api.post<ScenarioResponse>('/scenario/shutdown', { id: scenarioId, graceful }).then(res => res.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scenario', 'state'] });
      void queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });
};

// SCN-11: the scenario force-reconcile dialog. The preview is a pure read
// (believed-vs-desired per involved device + the forced chain a confirm would run);
// `enabled` gates it to the dialog being open on the ACTIVE scenario (409 otherwise).
export const useReconcilePreview = (scenarioId: string, enabled: boolean) => {
  return useQuery({
    queryKey: ['scenario', scenarioId, 'reconcile-preview'],
    queryFn: () =>
      api.get<ReconcilePreviewResponse>(`/scenario/${scenarioId}/reconcile_preview`).then(res => res.data),
    enabled: enabled && !!scenarioId,
    staleTime: 0, // believed state moves under us — refetch on every dialog open
  });
};

// Forces ONE device into the active scenario's desired state (diff skipped, driver
// idempotence guards bypassed, toggles claim their target). The call runs the device's
// full gated chain server-side — worst case a poll timeout, so it can take seconds.
export const useForceReconcileDevice = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ scenarioId, deviceId }: { scenarioId: string; deviceId: string }) =>
      api.post<ForceReconcileResponse>(`/scenario/${scenarioId}/force_reconcile`, { device_id: deviceId }).then(res => res.data),
    onSuccess: (_resp, { scenarioId, deviceId }) => {
      void queryClient.invalidateQueries({ queryKey: ['scenario', scenarioId, 'reconcile-preview'] });
      void queryClient.invalidateQueries({ queryKey: ['devices', deviceId, 'state'] });
    },
  });
};

// MQTT hooks
export const usePublishMQTT = () => {
  return useMutation({
    mutationFn: (message: MQTTMessage) =>
      api.post<MQTTPublishResponse>('/publish', message).then(res => res.data),
  });
};

// Query key helpers for consistent caching
export const queryKeys = {
  system: {
    info: ['system', 'info'] as const,
    config: ['system', 'config'] as const,
  },
  devices: {
    all: ['devices'] as const,
    configs: ['devices', 'configs'] as const,
    config: (deviceId: string) => ['devices', deviceId, 'config'] as const,
    state: (deviceId: string) => ['devices', deviceId, 'state'] as const,
    persistedState: (deviceId: string) => ['devices', deviceId, 'persisted'] as const,
    persistedStates: ['devices', 'persisted'] as const,
  },
  rooms: {
    all: ['rooms'] as const,
    detail: (roomId: string) => ['rooms', roomId] as const,
  },
  scenarios: {
    all: (roomId?: string) => ['scenarios', roomId] as const,
    detail: (scenarioId: string) => ['scenarios', 'definition', scenarioId] as const,
    state: ['scenario', 'state'] as const,
    specificState: (scenarioId: string) => ['scenarios', 'state', scenarioId] as const,
  },
}; 