import { useEffect } from 'react';
import { useRoomStore } from '../stores/useRoomStore';
import { useRooms, useAllDeviceConfigs, useScenarios } from './useApi';

// Type for device configuration from the API
interface DeviceConfig {
  device_id: string;
  device_name: string;
  room_id?: string;
  device_class?: string;
  config_class?: string;
  mqtt_progress_topic?: string;
  commands?: Record<string, any>;
  [key: string]: any; // For any additional properties
}

/**
 * Custom hook that synchronizes API data with Zustand stores
 * This bridges the gap between TanStack Query (API layer) and Zustand (state management)
 */
export const useDataSync = () => {
  const { setRooms, setDevices, setScenarios } = useRoomStore();
  
  // Fetch data using TanStack Query hooks
  const { data: roomsData, isSuccess: roomsSuccess, error: roomsError, isLoading: roomsLoading } = useRooms();
  const { data: devicesData, isSuccess: devicesSuccess, error: devicesError, isLoading: devicesLoading } = useAllDeviceConfigs();
  const { data: scenariosData, isSuccess: scenariosSuccess, error: scenariosError, isLoading: scenariosLoading } = useScenarios();

  // Sync rooms data
  useEffect(() => {
    if (roomsSuccess && roomsData) {
      const rooms = roomsData.map((room) => ({
        id: room.room_id,
        name: {
          en: room.names.en || room.names.english || Object.values(room.names)[0] || room.room_id,
          ru: room.names.ru || room.names.russian || Object.values(room.names)[0] || room.room_id,
        },
        devices: room.devices || [], // Include devices array from API
      }));
      setRooms(rooms);
    } else if (roomsError) {
      console.error('❌ Rooms API error:', roomsError);
    }
  }, [roomsData, roomsSuccess, roomsError, setRooms]);

  // Sync devices data - needs to be after rooms to map device->room relationships
  useEffect(() => {
    if (devicesSuccess && devicesData && roomsSuccess && roomsData) {
      // Create a map from device ID to room ID
      const deviceToRoomMap: Record<string, string> = {};
      roomsData.forEach((room) => {
        if (room.devices) {
          room.devices.forEach((deviceId) => {
            deviceToRoomMap[deviceId] = room.room_id;
          });
        }
      });
      
      // devicesData is a flat object where keys are device IDs and values are device configs
      const devices = Object.entries(devicesData as Record<string, DeviceConfig>).map(([deviceId, config]) => {
        const roomId = deviceToRoomMap[deviceId] || '';
        return {
          id: deviceId,
          name: {
            en: config.device_name || deviceId,
            ru: config.device_name || deviceId,
          },
          roomId: roomId, // Use the mapped room ID
          type: config.device_class || 'unknown',
        };
      });
      setDevices(devices);
    } else if (devicesError) {
      console.error('❌ Devices API error:', devicesError);
    }
  }, [devicesData, devicesSuccess, devicesError, roomsData, roomsSuccess, setDevices]);

  // Sync scenarios data
  useEffect(() => {
    if (scenariosSuccess && scenariosData) {
      const scenarios = scenariosData.map((scenario) => ({
        id: scenario.scenario_id,
        name: {
          en: scenario.name,
          ru: scenario.name, // API doesn't seem to have translations yet
        },
        description: scenario.description ? {
          en: scenario.description,
          ru: scenario.description,
        } : undefined,
        roomId: scenario.room_id || undefined,
      }));
      setScenarios(scenarios);
    } else if (scenariosError) {
      console.error('❌ Scenarios API error:', scenariosError);
    }
  }, [scenariosData, scenariosSuccess, scenariosError, setScenarios]);

  // Return loading states for components that might want to show loading indicators
  return {
    isLoadingRooms: roomsLoading,
    isLoadingDevices: devicesLoading,
    isLoadingScenarios: scenariosLoading,
    isLoading: roomsLoading || devicesLoading || scenariosLoading,
    errors: {
      rooms: roomsError,
      devices: devicesError,
      scenarios: scenariosError,
    },
  };
}; 