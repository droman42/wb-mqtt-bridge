import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

interface Room {
  id: string;
  name: { en: string; ru: string };
  devices?: string[]; // Device IDs that belong to this room
}

interface Device {
  id: string;
  name: { en: string; ru: string };
  roomId: string;
  type: string;
}

interface Scenario {
  id: string;
  name: { en: string; ru: string };
  description?: { en: string; ru: string };
  roomId?: string; // Room ID that this scenario belongs to
}

interface RoomState {
  rooms: Room[];
  devices: Device[];
  scenarios: Scenario[];
  selectedRoomId: string | null;
  selectedDeviceId: string | null;
  selectedScenarioId: string | null;
}

interface RoomActions {
  setRooms: (rooms: Room[]) => void;
  setDevices: (devices: Device[]) => void;
  setScenarios: (scenarios: Scenario[]) => void;
  selectRoom: (roomId: string | null) => void;
  selectDevice: (deviceId: string | null) => void;
  selectScenario: (scenarioId: string | null) => void;
  // Derived getters for filtered data
  getFilteredDevices: () => Device[];
  getFilteredScenarios: () => Scenario[];
}

export const useRoomStore = create<RoomState & RoomActions>()(
  immer((set, get) => ({
    rooms: [],
    devices: [],
    scenarios: [],
    selectedRoomId: null,
    selectedDeviceId: null,
    selectedScenarioId: null,

    setRooms: (rooms) => set((state) => {
      state.rooms = rooms;
    }),

    setDevices: (devices) => set((state) => {
      state.devices = devices;
    }),

    setScenarios: (scenarios) => set((state) => {
      state.scenarios = scenarios;
    }),

    selectRoom: (roomId) => set((state) => {
      state.selectedRoomId = roomId || null; // Ensure undefined becomes null
      // Clear device/scenario selection when room changes
      state.selectedDeviceId = null;
      state.selectedScenarioId = null;
    }),

    selectDevice: (deviceId) => set((state) => {
      state.selectedDeviceId = deviceId;
      state.selectedScenarioId = null; // Clear scenario when device is selected
    }),

    selectScenario: (scenarioId) => set((state) => {
      state.selectedScenarioId = scenarioId;
      state.selectedDeviceId = null; // Clear device when scenario is selected
    }),

    // Derived getters for filtered data
    getFilteredDevices: () => {
      const state = get();
      
      if (!state.selectedRoomId || state.selectedRoomId === 'undefined') {
        return state.devices; // If no room selected, show all devices
      }
      
      // Find the selected room to get its device list
      const selectedRoom = state.rooms.find(room => room.id === state.selectedRoomId);
      
      if (!selectedRoom || !selectedRoom.devices) {
        return []; // If room has no devices defined, return empty array
      }
      
      // Filter devices that belong to the selected room
      const filtered = state.devices.filter(device => 
        selectedRoom.devices!.includes(device.id)
      );
      return filtered;
    },

    getFilteredScenarios: () => {
      const state = get();
      
      if (!state.selectedRoomId || state.selectedRoomId === 'undefined') {
        return state.scenarios; // If no room selected, show all scenarios
      }
      
      // Filter scenarios that belong to the selected room
      const filtered = state.scenarios.filter(scenario => 
        scenario.roomId === state.selectedRoomId
      );
      return filtered;
    },
  }))
); 