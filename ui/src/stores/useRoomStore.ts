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
  category?: "device" | "appliance"; // New categorization field
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
  selectedApplianceId: string | null; // New appliance selection state
  selectedScenarioId: string | null;
}

interface RoomActions {
  setRooms: (rooms: Room[]) => void;
  setDevices: (devices: Device[]) => void;
  setScenarios: (scenarios: Scenario[]) => void;
  selectRoom: (roomId: string | null) => void;
  selectDevice: (deviceId: string | null) => void;
  selectAppliance: (applianceId: string | null) => void; // New appliance selection
  selectScenario: (scenarioId: string | null) => void;
  // Derived getters for filtered data
  getFilteredDevices: () => Device[];
  getFilteredAppliances: () => Device[]; // New appliance filtering
  getFilteredScenarios: () => Scenario[];
}

export const useRoomStore = create<RoomState & RoomActions>()(
  immer((set, get) => ({
    rooms: [],
    devices: [],
    scenarios: [],
    selectedRoomId: null,
    selectedDeviceId: null,
    selectedApplianceId: null,
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
      // Clear device/appliance/scenario selection when room changes
      state.selectedDeviceId = null;
      state.selectedApplianceId = null;
      state.selectedScenarioId = null;
    }),

    selectDevice: (deviceId) => set((state) => {
      state.selectedDeviceId = deviceId;
      state.selectedScenarioId = null; // Clear scenario when device is selected
    }),

    selectAppliance: (applianceId) => set((state) => {
      state.selectedApplianceId = applianceId;
      state.selectedDeviceId = null; // Clear device when appliance is selected
    }),

    selectScenario: (scenarioId) => set((state) => {
      state.selectedScenarioId = scenarioId;
      state.selectedDeviceId = null; // Clear device when scenario is selected
      state.selectedApplianceId = null; // Clear appliance when scenario is selected
    }),

    // Derived getters for filtered data
    getFilteredDevices: () => {
      const state = get();
      
      // First filter to only actual devices (not appliances)
      const devicesOnly = state.devices.filter(device => 
        device.category !== 'appliance'
      );
      
      if (!state.selectedRoomId || state.selectedRoomId === 'undefined') {
        return devicesOnly; // If no room selected, show all devices
      }
      
      // Find the selected room to get its device list
      const selectedRoom = state.rooms.find(room => room.id === state.selectedRoomId);
      
      if (!selectedRoom || !selectedRoom.devices) {
        return []; // If room has no devices defined, return empty array
      }
      
      // Filter devices that belong to the selected room
      const filtered = devicesOnly.filter(device => 
        selectedRoom.devices!.includes(device.id)
      );
      return filtered;
    },

    getFilteredAppliances: () => {
      const state = get();
      
      // First filter to only appliances
      const appliancesOnly = state.devices.filter(device => 
        device.category === 'appliance'
      );
      
      if (!state.selectedRoomId || state.selectedRoomId === 'undefined') {
        return appliancesOnly; // If no room selected, show all appliances
      }
      
      // Find the selected room to get its device list
      const selectedRoom = state.rooms.find(room => room.id === state.selectedRoomId);
      
      if (!selectedRoom || !selectedRoom.devices) {
        return []; // If room has no devices defined, return empty array
      }
      
      // Filter appliances that belong to the selected room
      const filtered = appliancesOnly.filter(appliance => 
        selectedRoom.devices!.includes(appliance.id)
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