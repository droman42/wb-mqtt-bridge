#!/usr/bin/env python3

import asyncio
import json
import os
import argparse
import socket
from typing import Dict, List, Optional, Any

import pyatv
import pyatv.interface
from pyatv import scan, connect
from pyatv.interface import BaseConfig
from pyatv.const import Protocol as ProtocolType

class AppleTVManager:
    """Utility class to manage Apple TV connections, pairing, and credentials."""
    
    def __init__(self, credentials_file: str = "apple_tv_credentials.json"):
        """Initialize the AppleTV manager.
        
        Args:
            credentials_file: Path to store/load credentials
        """
        self.credentials_file = credentials_file
        self.credentials = self._load_credentials()
    
    def _load_credentials(self) -> Dict[str, Any]:
        """Load stored credentials from file."""
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as err:
                print(f"Error loading credentials: {err}")
        return {}
    
    def _save_credentials(self) -> None:
        """Save credentials to file."""
        with open(self.credentials_file, "w") as f:
            json.dump(self.credentials, f, indent=2)
        print(f"Credentials saved to {self.credentials_file}")
    
    async def discover_devices(self, ip_addresses: Optional[List[str]] = None) -> List[BaseConfig]:
        """Discover Apple TV devices on the network.
        
        Args:
            ip_addresses: List of IP addresses to scan, or None to scan entire network
            
        Returns:
            List of discovered Apple TV configurations
        """
        loop = asyncio.get_event_loop()
        print("Scanning for Apple TV devices...")
        if ip_addresses:
            services = []
            for ip in ip_addresses:
                print(f"Scanning {ip}...")
                found = await scan(hosts=[ip], loop=loop)
                services.extend(found)
        else:
            services = await scan(loop=loop)
        
        if not services:
            print("No Apple TV devices found")
            return []
            
        print(f"Found {len(services)} Apple TV device(s):")
        for i, service in enumerate(services):
            print(f"  {i+1}. {service.name} ({service.address})")
            for protocol in service.services:
                protocol_name = protocol.protocol.name
                print(f"     - {protocol_name}")
        
        return services
    
    async def wake_device(self, ip_address: str) -> bool:
        """Wake an Apple TV device from sleep.
        
        This leverages Apple's Wake on Demand mechanism by initiating 
        connection attempts to the device's services, which triggers either 
        the device's network interface or a Bonjour Sleep Proxy to wake it.
        
        Args:
            ip_address: IP address of the device to wake
            
        Returns:
            True if wake attempt was initiated, False otherwise
        """
        print(f"Attempting to wake Apple TV at {ip_address}...")
        
        # Try to find the device even if in deep sleep
        # Scan with timeout=1 to speed up the process but allow discovery
        loop = asyncio.get_event_loop()
        found_devices = await scan(hosts=[ip_address], loop=loop)
        
        if not found_devices:
            print(f"Could not discover Apple TV at {ip_address}")
            
            # Try a direct TCP connection to common MRP ports even if discovery fails
            mrp_ports = [49152, 32498, 32499, 32500]  # Common MRP ports
            print("Attempting direct connection to MRP ports...")
            
            wake_attempted = False
            for port in mrp_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    sock.connect((ip_address, port))
                    sock.close()
                    print(f"Successfully connected to port {port}")
                    wake_attempted = True
                except (socket.timeout, ConnectionRefusedError, OSError):
                    pass
            
            if not wake_attempted:
                print("Could not connect to any MRP ports")
                return False
        else:
            device = found_devices[0]
            print(f"Found device: {device.name}")
            
            # Check if device is in deep sleep (this is indicated by tvOS 15+)
            if device.deep_sleep:
                print("Device appears to be in deep sleep")
            
            # Just initiating a connection attempt should trigger the wake mechanism
            try:
                # This connection attempt may fail, but that's expected and okay
                # The wake packets will be sent regardless
                atv = await connect(device, loop=loop)
                print("Connection established!")
                atv.close()
                return True
            except Exception as e:
                print(f"Connection failed as expected: {e}")
                print("Wake packets should have been sent")
                return True
        
        # The wake process has been initiated - it may take some time for the device to respond
        print("Wake signal sent. The device should wake up shortly.")
        print("You may need to run the scan command to check if it's available.")
        return True
    
    async def pair_device(self, config: BaseConfig, protocol_name: str = None) -> bool:
        """Pair with an Apple TV device and store credentials.
        
        Args:
            config: Device configuration to pair with
            protocol_name: Optional protocol name to use for pairing
            
        Returns:
            True if pairing was successful
        """
        try:
            device_id = config.address
            device_name = config.name or device_id
            
            print(f"\nStarting pairing with {device_name} ({device_id})")
            print("Available protocols for pairing:")
            
            # List all available protocols
            available_protocols = []
            for service in config.services:
                protocol_name_from_service = service.protocol.name
                requires_auth = service.requires_password
                print(f"  - {protocol_name_from_service}" + (" (requires password)" if requires_auth else ""))
                available_protocols.append(service.protocol)
            
            if not available_protocols:
                print("No protocols available for pairing")
                return False
            
            # Determine which protocol to use
            pairing_protocol = None
            
            # If a specific protocol was requested
            if protocol_name:
                for protocol in available_protocols:
                    if protocol.name.lower() == protocol_name.lower():
                        pairing_protocol = protocol
                        break
                
                if not pairing_protocol:
                    print(f"Protocol {protocol_name} not available for this device.")
                    return False
            # Otherwise prefer MRP over others
            elif ProtocolType.MRP in available_protocols:
                pairing_protocol = ProtocolType.MRP
            else:
                # Let the user select which protocol to pair with
                print("\nSelect protocol to pair with:")
                for i, protocol in enumerate(available_protocols):
                    print(f"  {i+1}. {protocol.name}")
                
                while True:
                    try:
                        choice = input("Enter protocol number (1-" + str(len(available_protocols)) + "): ")
                        protocol_index = int(choice) - 1
                        if 0 <= protocol_index < len(available_protocols):
                            pairing_protocol = available_protocols[protocol_index]
                            break
                        else:
                            print("Invalid selection. Please try again.")
                    except ValueError:
                        print("Please enter a number.")
                    except KeyboardInterrupt:
                        print("\nPairing cancelled.")
                        return False
            
            # Create pairing handler for the selected protocol
            print(f"\nPairing with protocol: {pairing_protocol.name}")
            
            # Now we need to create the pairing instance and start it
            try:
                loop = asyncio.get_event_loop()
                pairing = await pyatv.pair(config, protocol=pairing_protocol, loop=loop)
                await pairing.begin()
                
                # Display pairing information
                if pairing.device_provides_pin:
                    print("\nA PIN code should appear on your Apple TV.")
                    print("If no PIN appears within 10 seconds, press Ctrl+C to cancel and try a different protocol.")
                    
                    # Set a timeout for PIN input
                    try:
                        import signal
                        
                        def timeout_handler(signum, frame):
                            raise TimeoutError("No PIN appeared on the screen")
                        
                        # Set 30 second timeout
                        signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(30)
                        
                        pin = input("Enter PIN code shown on screen: ")
                        
                        # Cancel the timeout
                        signal.alarm(0)
                        
                        # Enter the PIN - different protocols have different methods
                        try:
                            if hasattr(pairing, 'enter_pin'):
                                await pairing.enter_pin(pin)
                            else:
                                pairing.pin(pin)
                        except Exception as e:
                            print(f"Error entering PIN: {e}")
                            await pairing.close()
                            return False
                    except TimeoutError:
                        print("\nNo PIN appeared within the timeout period.")
                        await pairing.close()
                        return False
                    except KeyboardInterrupt:
                        print("\nPairing cancelled.")
                        await pairing.close()
                        return False
                else:
                    # Generate a random PIN code
                    import random
                    pin = random.randint(1000, 9999)
                    print(f"\nEnter this PIN code on your Apple TV: {pin}")
                    pairing.pin(pin)
                    print("Waiting for PIN to be entered on the device...")
                    
                    # Loop until pairing is complete or user cancels
                    try:
                        for _ in range(30):  # Wait for up to 30 seconds
                            if pairing.has_paired:
                                break
                            print("Waiting for pairing to complete... Press Ctrl+C to cancel.")
                            await asyncio.sleep(1)
                        
                        if not pairing.has_paired:
                            print("Timed out waiting for PIN to be entered on the device.")
                            await pairing.close()
                            return False
                    except KeyboardInterrupt:
                        print("\nPairing cancelled.")
                        await pairing.close()
                        return False
                
                # Finish pairing
                await pairing.finish()
                
                if pairing.has_paired:
                    print(f"Successfully paired with {device_name} using {pairing_protocol.name}!")
                    
                    # Store credentials
                    device_id_str = str(device_id)
                    if device_id_str not in self.credentials:
                        self.credentials[device_id_str] = {
                            "name": device_name,
                            "protocols": {}
                        }
                    
                    # Update protocol credentials
                    try:
                        credentials = pairing.service.credentials
                        if isinstance(credentials, dict):
                            # Handle dictionary of credentials
                            for protocol, cred in credentials.items():
                                # Convert protocol to string if it's not already
                                protocol_key = protocol.name if hasattr(protocol, 'name') else str(protocol)
                                
                                self.credentials[device_id_str]["protocols"][protocol_key] = {
                                    "identifier": cred.identifier if hasattr(cred, 'identifier') else None,
                                    "credentials": cred.credentials if hasattr(cred, 'credentials') else str(cred),
                                    "data": cred.data if hasattr(cred, 'data') else None
                                }
                        else:
                            # Handle single credential
                            self.credentials[device_id_str]["protocols"][pairing_protocol.name] = {
                                "identifier": None,
                                "credentials": str(credentials),
                                "data": None
                            }
                        
                        self._save_credentials()
                        return True
                    except Exception as e:
                        print(f"Error storing credentials: {e}")
                        print("Pairing was successful, but credentials could not be saved.")
                        return True
                else:
                    print("Pairing failed. Please try again or use a different protocol.")
                    return False
            finally:
                try:
                    if 'pairing' in locals():
                        await pairing.close()
                except Exception as e:
                    print(f"Error closing pairing: {e}")
        except KeyboardInterrupt:
            print("\nPairing operation cancelled by user.")
            return False
        except Exception as e:
            print(f"Error during pairing: {e}")
            return False
    
    async def connect_to_device(self, ip_address: str) -> Optional[pyatv.interface.AppleTV]:
        """Connect to an Apple TV device using stored credentials.
        
        Args:
            ip_address: IP address of the device to connect to
            
        Returns:
            Connected AppleTV instance or None if connection failed
        """
        loop = asyncio.get_event_loop()
        
        ip_address_str = str(ip_address)
        if ip_address_str not in self.credentials:
            print(f"No stored credentials for {ip_address}")
            return None
        
        # Scan for the device to get the current configuration
        print(f"Scanning for Apple TV at {ip_address}...")
        atvs = await scan(hosts=[ip_address], loop=loop)
        if not atvs:
            print(f"No Apple TV found at {ip_address}")
            return None
        
        atv_config = atvs[0]
        device_name = self.credentials[ip_address_str]["name"]
        
        # Load stored credentials for each protocol
        for protocol_name, creds in self.credentials[ip_address_str]["protocols"].items():
            try:
                protocol = ProtocolType[protocol_name]
                atv_config.set_credentials(
                    protocol,
                    creds["credentials"]
                )
                print(f"Loaded credentials for {protocol_name}")
            except (KeyError, ValueError) as e:
                print(f"Error loading credentials for {protocol_name}: {e}")
        
        # Connect to the device
        print(f"Connecting to {device_name} ({ip_address})...")
        try:
            atv = await connect(atv_config, loop=loop)
            print(f"Successfully connected to {device_name}")
            return atv
        except Exception as e:
            print(f"Failed to connect: {e}")
            return None
    
    async def list_credentials(self) -> None:
        """List all stored credentials."""
        if not self.credentials:
            print("No stored credentials")
            return
        
        print("\nStored Apple TV credentials:")
        for ip, data in self.credentials.items():
            print(f"  - {data['name']} ({ip})")
            for protocol, cred in data["protocols"].items():
                print(f"    * {protocol}")
    
    def remove_device(self, ip_address: str) -> bool:
        """Remove stored credentials for a device.
        
        Args:
            ip_address: IP address of the device to remove
            
        Returns:
            True if credentials were removed
        """
        ip_address_str = str(ip_address)
        if ip_address_str in self.credentials:
            device_name = self.credentials[ip_address_str]["name"]
            del self.credentials[ip_address_str]
            self._save_credentials()
            print(f"Removed credentials for {device_name} ({ip_address})")
            return True
        else:
            print(f"No credentials found for {ip_address}")
            return False

async def main():
    """Main entry point for the Apple TV utility."""
    parser = argparse.ArgumentParser(description="Apple TV Management Utility")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for Apple TV devices")
    scan_parser.add_argument("--ip", "-i", nargs="+", help="IP addresses to scan")
    
    # Pair command
    pair_parser = subparsers.add_parser("pair", help="Pair with an Apple TV")
    pair_parser.add_argument("--ip", "-i", required=True, help="IP address to pair with")
    pair_parser.add_argument("--protocol", "-p", help="Protocol to use for pairing (AirPlay, MRP, Companion, RAOP)")
    
    # Connect command
    connect_parser = subparsers.add_parser("connect", help="Test connection to an Apple TV")
    connect_parser.add_argument("--ip", "-i", required=True, help="IP address to connect to")
    
    # Wake command
    wake_parser = subparsers.add_parser("wake", help="Wake an Apple TV from sleep")
    wake_parser.add_argument("--ip", "-i", required=True, help="IP address of the device to wake")
    
    # List command
    subparsers.add_parser("list", help="List all stored credentials")
    
    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove stored credentials")
    remove_parser.add_argument("--ip", "-i", required=True, help="IP address to remove")
    
    # Parse args
    args = parser.parse_args()
    
    # Create manager
    manager = AppleTVManager()
    
    # Execute command
    if args.command == "scan":
        await manager.discover_devices(args.ip)
    elif args.command == "pair":
        devices = await manager.discover_devices([args.ip])
        if devices:
            await manager.pair_device(devices[0], args.protocol)
        else:
            print(f"No Apple TV found at {args.ip}")
    elif args.command == "connect":
        atv = await manager.connect_to_device(args.ip)
        if atv:
            # Just demonstrate we're connected by getting device info
            print(f"Device info: {atv.device_info}")
            atv.close()
    elif args.command == "wake":
        await manager.wake_device(args.ip)
    elif args.command == "list":
        await manager.list_credentials()
    elif args.command == "remove":
        manager.remove_device(args.ip)
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main()) 