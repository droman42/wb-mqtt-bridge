import React, { useState } from 'react';
import { ChevronDownIcon, Cog6ToothIcon } from '@heroicons/react/24/solid';
import { useRoomStore } from '../stores/useRoomStore';
import { useSettingsStore } from '../stores/useSettingsStore';
import { Button } from './ui/button';

function Navbar() {
  const { 
    rooms, 
    devices, 
    scenarios, 
    selectedRoomId, 
    selectedDeviceId, 
    selectedScenarioId,
    selectRoom,
    selectDevice,
    selectScenario,
    getFilteredDevices,
    getFilteredScenarios
  } = useRoomStore();
  
  const { toggleStatePanel, toggleLogPanel } = useSettingsStore();

  // Local state for dropdown visibility
  const [dropdownOpen, setDropdownOpen] = useState<'rooms' | 'devices' | 'scenarios' | null>(null);

  const selectedRoom = rooms.find(r => r.id === selectedRoomId);
  const selectedDevice = devices.find(d => d.id === selectedDeviceId);
  const selectedScenario = scenarios.find(s => s.id === selectedScenarioId);

  // Use the filtered data from the store
  const filteredDevices = getFilteredDevices();
  const filteredScenarios = getFilteredScenarios();

  const handleDropdownToggle = (dropdown: 'rooms' | 'devices' | 'scenarios') => {
    setDropdownOpen(dropdownOpen === dropdown ? null : dropdown);
  };

  const handleRoomSelect = (roomId: string) => {
    selectRoom(roomId === '' ? null : roomId);
    setDropdownOpen(null);
  };

  const handleDeviceSelect = (deviceId: string) => {
    selectDevice(deviceId);
    setDropdownOpen(null);
  };

  const handleScenarioSelect = (scenarioId: string) => {
    selectScenario(scenarioId);
    setDropdownOpen(null);
  };

  return (
    <nav className="h-16 bg-card border-b border-border flex items-center justify-center px-4 relative">
      {/* Centered Selectors */}
      <div className="flex items-center space-x-4">
        {/* Room Dropdown */}
        <div className="relative">
          <Button 
            variant="outline" 
            className="flex items-center space-x-2"
            onClick={() => handleDropdownToggle('rooms')}
          >
            <span>{selectedRoom?.name.en || 'All Rooms'}</span>
            <ChevronDownIcon className="h-4 w-4" />
          </Button>
          
          {dropdownOpen === 'rooms' && (
            <div className="absolute top-full left-0 mt-1 w-48 bg-popover border border-border rounded-md shadow-lg z-50">
              <div className="py-1">
                <button
                  className="w-full px-3 py-2 text-left hover:bg-accent hover:text-accent-foreground text-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRoomSelect('');
                  }}
                >
                  All Rooms
                </button>
                {rooms.map((room) => {
                  return (
                    <button
                      key={room.id}
                      className="w-full px-3 py-2 text-left hover:bg-accent hover:text-accent-foreground text-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRoomSelect(room.id);
                      }}
                    >
                      {room.name.en}
                    </button>
                  );
                })}
                {rooms.length === 0 && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">No rooms available</div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Device Dropdown */}
        <div className="relative">
          <Button 
            variant="outline" 
            className="flex items-center space-x-2"
            onClick={() => handleDropdownToggle('devices')}
          >
            <span>{selectedDevice?.name.en || 'Select Device'}</span>
            <ChevronDownIcon className="h-4 w-4" />
          </Button>
          
          {dropdownOpen === 'devices' && (
            <div className="absolute top-full left-0 mt-1 w-48 bg-popover border border-border rounded-md shadow-lg z-50">
              <div className="py-1">
                {filteredDevices.map((device) => (
                  <button
                    key={device.id}
                    className="w-full px-3 py-2 text-left hover:bg-accent hover:text-accent-foreground text-sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeviceSelect(device.id);
                    }}
                  >
                    {device.name.en}
                  </button>
                ))}
                {filteredDevices.length === 0 && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">
                    {selectedRoomId ? 'No devices in this room' : 'No devices available'}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Scenario Dropdown */}
        <div className="relative">
          <Button 
            variant="outline" 
            className="flex items-center space-x-2"
            onClick={() => handleDropdownToggle('scenarios')}
          >
            <span>{selectedScenario?.name.en || 'Select Scenario'}</span>
            <ChevronDownIcon className="h-4 w-4" />
          </Button>
          
          {dropdownOpen === 'scenarios' && (
            <div className="absolute top-full left-0 mt-1 w-48 bg-popover border border-border rounded-md shadow-lg z-50">
              <div className="py-1">
                {filteredScenarios.map((scenario) => (
                  <button
                    key={scenario.id}
                    className="w-full px-3 py-2 text-left hover:bg-accent hover:text-accent-foreground text-sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleScenarioSelect(scenario.id);
                    }}
                  >
                    {scenario.name.en}
                  </button>
                ))}
                {filteredScenarios.length === 0 && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">
                    {selectedRoomId ? 'No scenarios for this room' : 'No scenarios available'}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right-side Controls */}
      <div className="absolute right-4 flex items-center space-x-2">
        {/* State Panel Toggle */}
        <Button 
          variant="ghost" 
          size="icon"
          onClick={toggleStatePanel}
          title="Toggle Device State Panel"
        >
          <Cog6ToothIcon className="h-5 w-5" />
        </Button>

        {/* Log Panel Toggle */}
        <Button 
          variant="ghost" 
          size="icon"
          onClick={toggleLogPanel}
          title="Toggle Log Panel"
        >
          <span className="text-xs">LOG</span>
        </Button>
      </div>

      {/* Click outside to close dropdowns */}
      {dropdownOpen && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={(e) => {
            setDropdownOpen(null);
          }}
        />
      )}
    </nav>
  );
}

export default Navbar; 