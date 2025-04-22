#!/usr/bin/env python3
import argparse
import asyncio
import socket
import ssl
import os
import sys
from datetime import datetime
import hashlib
import OpenSSL.crypto as crypto
import re
import time
from socket import AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST

def parse_args():
    parser = argparse.ArgumentParser(description="Extract SSL certificate from LG WebOS TV")
    parser.add_argument("--examples", action="store_true", help="Show usage examples")
    parser.add_argument("hostname", nargs='?', help="TV hostname or IP address")
    parser.add_argument("--port", type=int, default=3001, help="WebSocket port (default: 3001)")
    parser.add_argument("--output", help="Output certificate file (default: hostname_cert.pem)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing certificate file")
    parser.add_argument("--verify", action="store_true", help="Verify certificate after extraction")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--mac", help="MAC address of TV to send Wake-on-LAN packet if needed (format: xx:xx:xx:xx:xx:xx)")
    parser.add_argument("--wol-port", type=int, default=9, help="Port to use for Wake-on-LAN (default: 9)")
    parser.add_argument("--wol-broadcast", default="255.255.255.255", help="Broadcast address for Wake-on-LAN (default: 255.255.255.255)")
    parser.add_argument("--wol-retries", type=int, default=2, help="Number of WOL retries (default: 2)")
    parser.add_argument("--wol-wait", type=int, default=15, help="Seconds to wait after WOL before trying to connect again (default: 15)")
    
    args = parser.parse_args()
    
    # Check if examples was requested
    if args.examples:
        return args
        
    # Ensure hostname is provided if not showing examples
    if not args.hostname:
        parser.error("hostname is required unless --examples is used")
    
    # Set default output filename if not provided
    if not args.output:
        args.output = f"{args.hostname}_cert.pem"
    
    return args

def send_wol_packet(mac_address, ip_address="255.255.255.255", port=9, verbose=False):
    """Send a Wake-on-LAN magic packet to wake up a device.
    
    Args:
        mac_address (str): MAC address in format "xx:xx:xx:xx:xx:xx" or "xx-xx-xx-xx-xx-xx"
        ip_address (str): Broadcast IP address (default: 255.255.255.255)
        port (int): UDP port to send the packet to (default: 9)
        verbose (bool): Whether to print verbose output
        
    Returns:
        bool: True if packet sent successfully, False otherwise
    """
    try:
        # Validate MAC address format
        if not mac_address:
            print("No MAC address provided for Wake-on-LAN", file=sys.stderr)
            return False
            
        # Clean the MAC address (remove any separators and convert to lowercase)
        mac_address = re.sub(r'[^0-9a-fA-F]', '', mac_address).lower()
        
        if len(mac_address) != 12:
            print(f"Invalid MAC address: {mac_address}", file=sys.stderr)
            return False
            
        # Convert MAC address to bytes
        mac_bytes = bytes.fromhex(mac_address)
        
        # Create the magic packet (6 bytes of 0xFF followed by MAC address repeated 16 times)
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        
        # Send the packet
        sock = socket.socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        sock.sendto(magic_packet, (ip_address, port))
        sock.close()
        
        if verbose:
            print(f"Sent WOL packet to {':'.join([mac_address[i:i+2] for i in range(0, 12, 2)])} via {ip_address}:{port}")
        return True
            
    except Exception as e:
        print(f"Failed to send WOL packet: {str(e)}", file=sys.stderr)
        return False

def is_host_reachable(hostname, port, timeout=3, mac_address=None, wol_retries=2, wol_wait=15, wol_port=9, wol_broadcast="255.255.255.255", verbose=False):
    """Check if host is reachable by attempting a TCP connection.
    
    If the host is not reachable and a MAC address is provided, sends a Wake-on-LAN
    packet to attempt to wake up the device, and then checks again after waiting.
    
    Args:
        hostname (str): Hostname or IP address of the device
        port (int): Port to check connection on
        timeout (int): Timeout for connection attempts in seconds
        mac_address (str, optional): MAC address for WOL if device is unreachable
        wol_retries (int): Number of WOL attempts to make
        wol_wait (int): Seconds to wait after WOL before trying to connect again
        wol_port (int): Port to use for Wake-on-LAN
        wol_broadcast (str): Broadcast address for Wake-on-LAN
        verbose (bool): Whether to print verbose output
        
    Returns:
        bool: True if host is or becomes reachable, False otherwise
    """
    # First attempt to connect directly
    try:
        socket.create_connection((hostname, port), timeout=timeout)
        if verbose:
            print(f"Host {hostname}:{port} is reachable")
        return True
    except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError):
        if verbose:
            print(f"Host {hostname}:{port} is not reachable on first attempt")
        
        # If MAC address is provided, try Wake-on-LAN
        if mac_address:
            if verbose:
                print(f"Attempting to wake up {hostname} with Wake-on-LAN using MAC {mac_address}")
            
            for attempt in range(wol_retries):
                # Send WOL packet
                wol_sent = send_wol_packet(mac_address, wol_broadcast, wol_port, verbose)
                if not wol_sent:
                    if verbose:
                        print(f"Failed to send WOL packet on attempt {attempt+1}/{wol_retries}")
                    continue
                
                # Wait for device to boot
                if verbose:
                    print(f"Waiting {wol_wait} seconds for device to boot...")
                time.sleep(wol_wait)
                
                # Try to connect again
                try:
                    socket.create_connection((hostname, port), timeout=timeout)
                    if verbose:
                        print(f"Host {hostname}:{port} is now reachable after Wake-on-LAN")
                    return True
                except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError):
                    if verbose:
                        print(f"Host {hostname}:{port} is still not reachable after Wake-on-LAN (attempt {attempt+1}/{wol_retries})")
            
            if verbose:
                print(f"Failed to reach {hostname}:{port} after {wol_retries} Wake-on-LAN attempts")
        
        return False

def extract_certificate(hostname, port, verbose=False):
    """Extract SSL certificate from the given hostname and port."""
    if verbose:
        print(f"Creating SSL context without verification...")
    
    # Create SSL context without verification
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    
    try:
        if verbose:
            print(f"Connecting to {hostname}:{port}...")
        
        # Connect to the server and get the certificate
        with socket.create_connection((hostname, port)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert_bin = ssock.getpeercert(binary_form=True)
                if verbose:
                    print("Certificate obtained successfully")
                return cert_bin
    except Exception as e:
        print(f"Error extracting certificate: {e}", file=sys.stderr)
        return None

def save_certificate(cert_bin, output_file, force=False, verbose=False):
    """Save the binary certificate to a PEM file."""
    # Check if file exists and force flag is not set
    if os.path.exists(output_file) and not force:
        print(f"Error: Output file {output_file} already exists. Use --force to overwrite.", file=sys.stderr)
        return False
    
    try:
        # Convert binary certificate to PEM format
        x509 = crypto.load_certificate(crypto.FILETYPE_ASN1, cert_bin)
        pem_data = crypto.dump_certificate(crypto.FILETYPE_PEM, x509)
        
        # Save to file
        with open(output_file, 'wb') as f:
            f.write(pem_data)
        
        if verbose:
            print(f"Certificate saved to {output_file}")
        
        return True
    except Exception as e:
        print(f"Error saving certificate: {e}", file=sys.stderr)
        return False

def verify_certificate(hostname, port, cert_file, verbose=False):
    """Verify that the saved certificate matches the one from the server."""
    if verbose:
        print(f"Verifying certificate against {hostname}:{port}...")
    
    try:
        # Load the saved certificate
        with open(cert_file, 'rb') as f:
            saved_cert_data = f.read()
            saved_cert = crypto.load_certificate(crypto.FILETYPE_PEM, saved_cert_data)
            saved_cert_bin = crypto.dump_certificate(crypto.FILETYPE_ASN1, saved_cert)
            saved_fingerprint = hashlib.sha256(saved_cert_bin).hexdigest()
        
        # Get the current certificate
        current_cert_bin = extract_certificate(hostname, port, verbose)
        if not current_cert_bin:
            print("Could not get current certificate for verification", file=sys.stderr)
            return False
        
        current_fingerprint = hashlib.sha256(current_cert_bin).hexdigest()
        
        # Compare the fingerprints
        if saved_fingerprint == current_fingerprint:
            if verbose:
                print("Certificate verification passed: Certificate matches the one from the server")
            return True
        else:
            print("Certificate verification failed: Certificate does not match the one from the server", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Error verifying certificate: {e}", file=sys.stderr)
        return False

def print_certificate_info(cert_bin):
    """Print detailed information about the certificate."""
    try:
        x509 = crypto.load_certificate(crypto.FILETYPE_ASN1, cert_bin)
        
        # Get issuer information
        issuer = x509.get_issuer().get_components()
        issuer_str = ', '.join([f"{name.decode()}={value.decode()}" for name, value in issuer])
        
        # Get validity dates
        not_before_str = x509.get_notBefore()
        not_after_str = x509.get_notAfter()
        
        # Handle potential None values
        if not_before_str is not None:
            not_before = datetime.strptime(not_before_str.decode(), "%Y%m%d%H%M%SZ")
            not_before_formatted = not_before.strftime('%Y-%m-%d %H:%M:%S')
        else:
            not_before_formatted = "Unknown"
            
        if not_after_str is not None:
            not_after = datetime.strptime(not_after_str.decode(), "%Y%m%d%H%M%SZ")
            not_after_formatted = not_after.strftime('%Y-%m-%d %H:%M:%S')
        else:
            not_after_formatted = "Unknown"
        
        # Get fingerprint
        fingerprint = hashlib.sha256(cert_bin).hexdigest()
        
        # Print certificate information
        print("\n=== Certificate Information ===")
        print(f"Issuer: {issuer_str}")
        print(f"Valid from: {not_before_formatted} UTC")
        print(f"Valid until: {not_after_formatted} UTC")
        print(f"SHA-256 Fingerprint: {fingerprint}")
        print(f"Subject Alternative Names: {get_subject_alt_names(x509)}")
        print("\n=== Configuration Hint ===")
        print("Add the following to your TV device configuration:")
        print("```")
        print("\"tv\": {")
        print("    ...,")
        print("    \"secure\": true,")
        print(f"    \"cert_file\": \"{os.path.abspath(args.output)}\"")
        print("}")
        print("```")
        
    except Exception as e:
        print(f"Error printing certificate information: {e}", file=sys.stderr)

def get_subject_alt_names(x509):
    """Extract Subject Alternative Names from certificate."""
    san_list = []
    
    for i in range(x509.get_extension_count()):
        ext = x509.get_extension(i)
        if ext.get_short_name() == b'subjectAltName':
            san_text = ext.__str__()
            # Parse the SAN text (usually in format: "DNS:example.com, DNS:www.example.com")
            for name in san_text.split(', '):
                if ':' in name:
                    san_list.append(name.strip())
    
    return ', '.join(san_list) if san_list else "None"

def print_usage_examples():
    """Print usage examples for the script."""
    print("\nUsage Examples:")
    print("===============")
    print("\n1. Basic certificate extraction:")
    print("   ./extract_lg_tv_cert.py 192.168.1.100")
    print("\n2. Save certificate to a specific file:")
    print("   ./extract_lg_tv_cert.py 192.168.1.100 --output my_tv_cert.pem")
    print("\n3. Extract certificate with verbose output and verification:")
    print("   ./extract_lg_tv_cert.py 192.168.1.100 --verbose --verify")
    print("\n4. Use Wake-on-LAN if TV is off:")
    print("   ./extract_lg_tv_cert.py 192.168.1.100 --mac 11:22:33:44:55:66 --wol-wait 20")
    print("\n5. Full usage with all options:")
    print("   ./extract_lg_tv_cert.py 192.168.1.100 --output tv_cert.pem --force --verify --verbose \\")
    print("      --mac 11:22:33:44:55:66 --wol-port 9 --wol-broadcast 192.168.1.255 \\")
    print("      --wol-retries 3 --wol-wait 15")

async def main():
    # Parse command line arguments
    global args
    args = parse_args()
    
    # Show usage examples if requested
    if args.examples:
        print_usage_examples()
        return 0
    
    if args.verbose:
        print(f"Checking if {args.hostname}:{args.port} is reachable...")
    
    # Check if host is reachable
    if not is_host_reachable(
        hostname=args.hostname, 
        port=args.port,
        timeout=3,
        mac_address=args.mac,
        wol_retries=args.wol_retries,
        wol_wait=args.wol_wait,
        wol_port=args.wol_port,
        wol_broadcast=args.wol_broadcast,
        verbose=args.verbose
    ):
        print(f"Error: Could not connect to {args.hostname}:{args.port}. Is the TV powered on?", file=sys.stderr)
        return 1
    
    if args.verbose:
        print(f"Host {args.hostname}:{args.port} is reachable")
    
    # Extract the certificate
    print(f"Extracting certificate from {args.hostname}:{args.port}...")
    cert_bin = extract_certificate(args.hostname, args.port, args.verbose)
    if not cert_bin:
        print("Failed to extract certificate", file=sys.stderr)
        return 1
    
    # Save the certificate
    print(f"Saving certificate to {args.output}...")
    if not save_certificate(cert_bin, args.output, args.force, args.verbose):
        return 1
    
    # Print certificate information
    print_certificate_info(cert_bin)
    
    # Verify the certificate if requested
    if args.verify:
        print("\nVerifying the saved certificate...")
        if verify_certificate(args.hostname, args.port, args.output, args.verbose):
            print("Certificate verification successful")
        else:
            print("Certificate verification failed", file=sys.stderr)
            return 1
    
    print(f"\nCertificate extraction complete. File saved to: {args.output}")
    
    # Print usage examples at the end for reference
    if args.verbose:
        print("\nHint: Use --examples to see more usage examples")
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 