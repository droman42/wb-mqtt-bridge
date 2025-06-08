import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import type {
  DeviceAction,
  MQTTMessage,
  SwitchScenarioRequest,
  ActionRequest,
  SystemInfo,
  SystemConfig,
  ReloadResponse,
  RoomDefinitionResponse,
  ScenarioDefinition,
  ScenarioState,
  ScenarioResponse,
  Group,
  GroupedActionsResponse,
  GroupActionsResponse,
  CommandResponse,
  BaseDeviceState,
  DeviceState,
  MQTTPublishResponse,
} from '../types/api';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://192.168.110.250:8000',
  timeout: 10000,
});

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
    queryFn: () => api.get<SystemConfig>('/config/system').then(res => res.data),
  });
};

export const useReloadSystem = () => {
  return useMutation({
    mutationFn: () => api.post<ReloadResponse>('/system/reload').then(res => res.data),
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
    refetchInterval: 5000, // Poll every 5 seconds for real-time updates
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
    queryFn: () => api.get<any>('/devices/persisted_states').then(res => res.data),
  });
};

export const useExecuteDeviceAction = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, action }: { deviceId: string; action: DeviceAction }) =>
      api.post<CommandResponse>(`/devices/${deviceId}/action`, action).then(res => res.data),
    onSuccess: (_, { deviceId }) => {
      // Invalidate device state to refetch latest data
      queryClient.invalidateQueries({ queryKey: ['devices', deviceId, 'state'] });
    },
  });
};

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

export const useSwitchScenario = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: SwitchScenarioRequest) =>
      api.post<ScenarioResponse>('/scenario/switch', request).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenario', 'state'] });
      queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });
};

export const useExecuteRoleAction = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: ActionRequest) =>
      api.post<ScenarioResponse>('/scenario/role/action', request).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenario', 'state'] });
      queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });
};

// Group hooks
export const useGroups = () => {
  return useQuery({
    queryKey: ['groups'],
    queryFn: () => api.get<Group[]>('/groups').then(res => res.data),
  });
};

export const useDeviceGroups = (deviceId: string) => {
  return useQuery({
    queryKey: ['devices', deviceId, 'groups'],
    queryFn: () => api.get<GroupedActionsResponse>(`/devices/${deviceId}/groups`).then(res => res.data),
    enabled: !!deviceId,
  });
};

export const useGroupActions = (deviceId: string, groupId: string) => {
  return useQuery({
    queryKey: ['devices', deviceId, 'groups', groupId, 'actions'],
    queryFn: () => api.get<GroupActionsResponse>(`/devices/${deviceId}/groups/${groupId}/actions`).then(res => res.data),
    enabled: !!(deviceId && groupId),
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
    groups: (deviceId: string) => ['devices', deviceId, 'groups'] as const,
    groupActions: (deviceId: string, groupId: string) => ['devices', deviceId, 'groups', groupId, 'actions'] as const,
  },
  rooms: {
    all: ['rooms'] as const,
    detail: (roomId: string) => ['rooms', roomId] as const,
  },
  scenarios: {
    all: (roomId?: string) => ['scenarios', roomId] as const,
    detail: (scenarioId: string) => ['scenarios', 'definition', scenarioId] as const,
    state: ['scenario', 'state'] as const,
  },
  groups: {
    all: ['groups'] as const,
  },
}; 