from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, validator
import os

class MQTTBrokerConfig(BaseModel):
    """Schema for MQTT broker configuration."""
    host: str
    port: int
    client_id: str
    auth: Optional[Dict[str, str]] = None
    keepalive: int = 60

class EmotivaConfig(BaseModel):
    """Schema for Emotiva XMC2 device configuration."""
    host: str
    port: int = 7002
    mac: Optional[str] = None
    update_interval: int = 60
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    retry_delay: Optional[float] = None
    force_connect: bool = False

class AppleTVProtocolConfig(BaseModel):
    """Schema for Apple TV protocol configuration."""
    identifier: Optional[str] = None
    credentials: str
    data: Optional[Any] = None

class AppleTVConfig(BaseModel):
    """Schema for Apple TV device configuration."""
    ip_address: str
    name: Optional[str] = None
    protocols: Dict[str, AppleTVProtocolConfig]
    gesture_threshold: float = 10.0
    touch_delay: float = 0.1
    select_delay: float = 0.2

class LgTvConfig(BaseModel):
    """Schema for LG WebOS TV device configuration."""
    ip_address: str
    mac_address: Optional[str] = None
    broadcast_ip: Optional[str] = None
    secure: bool = True
    client_key: Optional[str] = None
    cert_file: Optional[str] = None
    ssl_options: Optional[Dict[str, Any]] = None
    timeout: int = 15
    reconnect_interval: Optional[int] = None
    
    def model_post_init(self, __context: Any) -> None:
        """Validate that cert_file exists if secure=True"""
        if self.secure and self.cert_file:
            if not os.path.exists(self.cert_file):
                raise ValueError(f"Certificate file {self.cert_file} does not exist")

class BroadlinkConfig(BaseModel):
    """Schema for Broadlink device configuration."""
    host: str
    mac: str
    device_code: str
    timeout: Optional[int] = None
    retry_count: Optional[int] = None

class AuralicConfig(BaseModel):
    """Configuration for Auralic device."""
    ip_address: str
    update_interval: int = 10  # seconds
    discovery_mode: bool = False
    device_url: Optional[str] = None
    # IR control parameters
    ir_power_on_topic: Optional[str] = Field(
        None,
        description="MQTT topic to send IR power on command (required for true power on from deep sleep)"
    )
    ir_power_off_topic: Optional[str] = Field(
        None,
        description="MQTT topic to send IR power off command (required for true power off)"
    )
    device_boot_time: int = Field(
        15,
        description="Time in seconds to wait for device to boot after IR power on",
        ge=5,  # At least 5 seconds
        le=60  # At most 60 seconds
    )

class CommandParameterDefinition(BaseModel):
    """Schema for command parameter definition."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Data type (e.g., 'string', 'integer', 'float', 'boolean', 'range')")
    required: bool = Field(..., description="Whether this parameter must be provided")
    default: Optional[Any] = Field(None, description="Default value if parameter is not provided and not required")
    min: Optional[float] = Field(None, description="Minimum allowed value (used with type: 'range')")
    max: Optional[float] = Field(None, description="Maximum allowed value (used with type: 'range')")
    description: Optional[str] = Field(None, description="Human-readable description")

# Command configuration models
class BaseCommandConfig(BaseModel):
    """Base schema for command configuration."""
    action: Optional[str] = Field(None, description="Action identifier for this command")
    description: Optional[str] = Field(None, description="Human-readable description of the command")
    group: Optional[str] = Field(None, description="Functional group this command belongs to")
    params: Optional[List[CommandParameterDefinition]] = Field(
        None, 
        description="Parameter definitions for this command"
    )

class StandardCommandConfig(BaseCommandConfig):
    """Standard command configuration with no additional fields."""
    pass

class IRCommandConfig(BaseCommandConfig):
    """Command configuration for IR-controlled devices."""
    location: str = Field(..., description="IR blaster location identifier")
    rom_position: str = Field(..., description="ROM position for the IR code")

# Device-specific parameter models
class RevoxA77ReelToReelParams(BaseModel):
    """Parameters specific to Revox A77 Reel-to-Reel device."""
    sequence_delay: int = Field(5, description="Delay between sequence steps in seconds")

# Base device configuration model
class BaseDeviceConfig(BaseModel):
    """Base schema for device configuration."""
    device_id: str
    device_name: str
    # New required fields for dynamic class loading
    device_class: str = Field(..., description="The device implementation class name (e.g., 'LgTv')")
    config_class: str = Field(..., description="The configuration model class name (e.g., 'LgTvDeviceConfig')")
    commands: Dict[str, BaseCommandConfig] = Field(default_factory=dict)
    
    # Wirenboard virtual device emulation configuration
    enable_wb_emulation: bool = Field(True, description="Enable Wirenboard virtual device emulation")
    wb_controls: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Custom Wirenboard control definitions")
    wb_state_mappings: Optional[Dict[str, Union[str, List[str]]]] = Field(None, description="Custom state field to WB control mappings")

    @validator('device_class')
    def validate_device_class(cls, v):
        """Validate that device_class is not empty."""
        if not v or not v.strip():
            raise ValueError("device_class must not be empty")
        return v

    @validator('config_class')
    def validate_config_class(cls, v):
        """Validate that config_class is not empty."""
        if not v or not v.strip():
            raise ValueError("config_class must not be empty")
        return v
    
    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, BaseCommandConfig]:
        """
        Process raw command definitions into properly typed command objects.
        Each device config subclass can override this for custom command processing.
        
        Args:
            commands_data: Raw command data dictionary
            
        Returns:
            Dictionary of processed command objects
        """
        processed_commands = {}
        
        for cmd_name, cmd_config in commands_data.items():
            # Skip if not a dictionary
            if not isinstance(cmd_config, dict):
                raise ValueError(f"Command {cmd_name} has invalid format, must be a dictionary")
            
            # Use standard command for base implementation
            processed_commands[cmd_name] = StandardCommandConfig(**cmd_config)
                
        return processed_commands
    
    @classmethod
    def create_from_dict(cls, config_data: Dict[str, Any]) -> 'BaseDeviceConfig':
        """
        Create a configuration instance from a dictionary, processing commands appropriately.
        
        Args:
            config_data: Raw configuration dictionary
            
        Returns:
            Initialized configuration object
            
        Raises:
            ValueError: If the configuration is invalid
        """
        # Create a copy to avoid modifying the original
        config = dict(config_data)
        
        # Process commands if present
        if "commands" in config and isinstance(config["commands"], dict):
            config["commands"] = cls.process_commands(config["commands"])
            
        # Create and return the instance
        return cls(**config)

# Device-specific configuration models
class WirenboardIRDeviceConfig(BaseDeviceConfig):
    """Configuration for Wirenboard IR devices."""
    commands: Dict[str, IRCommandConfig] = Field(default_factory=dict)
    
    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, IRCommandConfig]:
        """
        Process commands specifically for Wirenboard IR devices.
        
        Args:
            commands_data: Raw command data
            
        Returns:
            Dictionary of processed IR commands
        """
        processed_commands = {}
        
        for cmd_name, cmd_config in commands_data.items():
            if not isinstance(cmd_config, dict):
                raise ValueError(f"Command {cmd_name} has invalid format, must be a dictionary")
                
            # Validate IR command structure
            if "location" not in cmd_config or "rom_position" not in cmd_config:
                raise ValueError(
                    f"IR Command {cmd_name} missing required fields: location and rom_position"
                )
                
            # Create IR command
            processed_commands[cmd_name] = IRCommandConfig(**cmd_config)
                
        return processed_commands

class RevoxA77ReelToReelConfig(BaseDeviceConfig):
    """Configuration for Revox A77 Reel-to-Reel device."""
    commands: Dict[str, IRCommandConfig] = Field(default_factory=dict)
    reel_to_reel: RevoxA77ReelToReelParams
    
    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, IRCommandConfig]:
        """
        Process commands specifically for Revox A77 Reel-to-Reel devices.
        Uses the same IR command processing as Wirenboard.
        
        Args:
            commands_data: Raw command data
            
        Returns:
            Dictionary of processed IR commands
        """
        return WirenboardIRDeviceConfig.process_commands(commands_data)

class BroadlinkKitchenHoodConfig(BaseDeviceConfig):
    """Configuration for Broadlink kitchen hood device."""
    commands: Dict[str, BaseCommandConfig] = Field(default_factory=dict)
    broadlink: BroadlinkConfig
    rf_codes: Dict[str, Dict[str, str]] = Field(
        ...,
        description="RF codes mapped by category (light, speed) and state"
    )
    
    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, BaseCommandConfig]:
        """
        Process commands specifically for Broadlink kitchen hood devices.
        
        Args:
            commands_data: Raw command data
            
        Returns:
            Dictionary of processed commands
        """
        processed_commands = {}
        
        for cmd_name, cmd_config in commands_data.items():
            if not isinstance(cmd_config, dict):
                raise ValueError(f"Command {cmd_name} has invalid format, must be a dictionary")
                
            # Use StandardCommandConfig for all commands
            processed_commands[cmd_name] = StandardCommandConfig(**cmd_config)
                
        return processed_commands

class LgTvDeviceConfig(BaseDeviceConfig):
    """Configuration for LG TV device."""
    commands: Dict[str, StandardCommandConfig] = Field(default_factory=dict)
    tv: LgTvConfig

class AppleTVDeviceConfig(BaseDeviceConfig):
    """Configuration for Apple TV device."""
    commands: Dict[str, StandardCommandConfig] = Field(default_factory=dict)
    apple_tv: AppleTVConfig

class EmotivaXMC2DeviceConfig(BaseDeviceConfig):
    """Configuration for Emotiva XMC2 device."""
    commands: Dict[str, StandardCommandConfig] = Field(default_factory=dict)
    emotiva: EmotivaConfig

class AuralicDeviceConfig(BaseDeviceConfig):
    """Configuration for Auralic device."""
    commands: Dict[str, StandardCommandConfig] = Field(default_factory=dict)
    auralic: AuralicConfig
    
    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, StandardCommandConfig]:
        """
        Process commands specifically for Auralic devices.
        
        Args:
            commands_data: Raw command data
            
        Returns:
            Dictionary of processed standard commands
        """
        processed_commands = {}
        
        for cmd_name, cmd_config in commands_data.items():
            if not isinstance(cmd_config, dict):
                raise ValueError(f"Command {cmd_name} has invalid format, must be a dictionary")
                
            # Create standard command
            processed_commands[cmd_name] = StandardCommandConfig(**cmd_config)
                
        return processed_commands

class PersistenceConfig(BaseModel):
    """Configuration for the persistence layer."""
    db_path: str = Field(default="data/state_store.db", description="Path to the SQLite database file")

class MaintenanceConfig(BaseModel):
    """Configuration for system maintenance settings."""
    duration: int = Field(..., description="Maintenance duration in minutes")
    topic: str = Field(..., description="MQTT topic to monitor for maintenance status")

class SystemConfig(BaseModel):
    """Schema for system configuration."""
    service_name: str = Field(default="MQTT Web Service", description="Name of the service")
    mqtt_broker: MQTTBrokerConfig
    web_service: Dict[str, Any]
    log_level: str
    log_file: str
    loggers: Optional[Dict[str, str]] = None
    # Remove devices dictionary from required fields and make it optional
    devices: Optional[Dict[str, Dict[str, Any]]] = None
    groups: Dict[str, str] = Field(default_factory=dict)  # Internal name -> Display name
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    maintenance: Optional[MaintenanceConfig] = Field(None, description="Maintenance configuration settings")
    # Add explicit device directory configuration
    device_directory: str = Field(default="devices", description="Directory containing device configuration files") 