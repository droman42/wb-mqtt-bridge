"""Pydantic models for scenario WB virtual device configurations."""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Union
from wb_mqtt_bridge.infrastructure.config.models import StandardCommandConfig
from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition


class ScenarioWBConfig(BaseModel):
    """Virtual WB configuration generated from scenario definition.
    
    This model creates a virtual BaseDeviceConfig-compatible configuration
    from scenario definitions without modifying scenario config files.
    Uses scenario_id as device_id and name as device_name for virtual abstraction.
    """
    
    # Required BaseDeviceConfig-compatible fields
    device_id: str = Field(..., description="Maps to scenario_id")
    device_name: str = Field(..., description="Maps to scenario.name")
    device_class: str = Field(default="Scenario", description="Virtual device class")
    config_class: str = Field(default="ScenarioWBConfig", description="Config type identifier")
    commands: Dict[str, StandardCommandConfig] = Field(
        default_factory=dict, 
        description="Virtual commands generated from scenario structure"
    )
    
    # WB emulation fields
    enable_wb_emulation: bool = Field(default=True, description="Enable WB virtual device")
    wb_controls: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None, 
        description="Custom WB control overrides"
    )
    wb_state_mappings: Optional[Dict[str, Union[str, List[str]]]] = Field(
        default=None, 
        description="State synchronization mappings"
    )
    
    # Virtual metadata (excluded from serialization) - Pydantic private attributes
    class Config:
        # Allow private attributes
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        super().__init__(**data)
        # Set private attributes after initialization
        self._source_scenario: Optional[ScenarioDefinition] = data.get('_source_scenario')
        self._virtual_entity_type: str = "scenario"
    
    @classmethod
    def from_scenario(
        cls, 
        scenario_definition: ScenarioDefinition, 
        device_manager
    ) -> "ScenarioWBConfig":
        """Factory method to create virtual config from scenario definition.
        
        Args:
            scenario_definition: The scenario definition to virtualize
            device_manager: Device manager for role command extraction
            
        Returns:
            ScenarioWBConfig: Virtual configuration with generated commands
        """
        instance = cls(
            device_id=scenario_definition.scenario_id,
            device_name=scenario_definition.name,
            commands=cls._generate_virtual_commands(scenario_definition, device_manager),
            _source_scenario=scenario_definition
        )
        return instance
    
    @staticmethod
    def _generate_virtual_commands(
        scenario: ScenarioDefinition, 
        device_manager
    ) -> Dict[str, StandardCommandConfig]:
        """Generate virtual commands from scenario structure.
        
        Creates startup/shutdown commands as critical power group commands,
        and role-based commands inherited from devices with preserved typing.
        
        Args:
            scenario: Scenario definition
            device_manager: Device manager for command extraction
            
        Returns:
            Dict of command name to StandardCommandConfig
        """
        commands = {}
        
        # Critical: Startup/Shutdown as power group commands (supercritical per requirements)
        commands["startup"] = StandardCommandConfig(
            action="execute_startup_sequence",
            description="Start scenario",
            group="power",
            params=[]
        )
        
        commands["shutdown"] = StandardCommandConfig(
            action="execute_shutdown_sequence", 
            description="Stop scenario",
            group="power",
            params=[]
        )
        
        # Roles that should only be used for startup/shutdown sequences, not exposed as virtual commands
        startup_only_roles = {"inputs"}
        
        # Role-based inheritance with preserved command structure
        for role, device_id in scenario.roles.items():
            # Skip roles that should only be used in startup/shutdown sequences
            if role in startup_only_roles:
                continue
                
            device = device_manager.get_device(device_id)
            if device:
                role_commands = ScenarioWBConfig._extract_role_commands(device, role)
                for cmd_name, cmd_config in role_commands.items():
                    virtual_name = f"{role}_{cmd_name}"
                    
                    # ✅ Always convert to StandardCommandConfig regardless of source type
                    # This preserves the essential command information while ensuring type consistency
                    commands[virtual_name] = StandardCommandConfig(
                        action=cmd_config.action,  # Preserve original action name for delegation
                        description=f"{role.title()} {cmd_config.description or cmd_name}",
                        group=role,  # Role becomes the group
                        params=getattr(cmd_config, 'params', []) or []  # Preserve original parameters
                    )
        
        return commands
    
    @staticmethod
    def _extract_role_commands(device, role: str) -> Dict[str, Any]:
        """Extract commands from device that match the role's functional area.
        
        Maps role names to expected command groups and extracts matching
        commands from the device's available commands.
        
        Args:
            device: Device instance to extract commands from
            role: Role name (e.g., 'playback', 'volume')
            
        Returns:
            Dict of command name to command config for the role
        """
        available_commands = device.get_available_commands()
        role_commands = {}
        
        # Map role to expected command groups (leverages existing group system)
        role_group_mapping = {
            "playback": ["playback"],
            "volume": ["volume"], 
            "power": ["power"],
            "inputs": ["inputs", "apps"],
            "menu": ["menu", "navigation"],
            "display": ["screen", "display"]
        }
        
        expected_groups = role_group_mapping.get(role, [role])  # Fallback to role name as group
        
        for cmd_name, cmd_config in available_commands.items():
            if hasattr(cmd_config, 'group') and cmd_config.group in expected_groups:
                role_commands[cmd_name] = cmd_config
        
        return role_commands
    
    def get_virtual_device_metadata(self) -> Dict[str, Any]:
        """Get virtual device metadata for WB device registration.
        
        Returns:
            Dict with device metadata compatible with WB protocol
        """
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_class": self.device_class,
            "virtual_entity_type": self._virtual_entity_type,
            "enable_wb_emulation": self.enable_wb_emulation
        } 