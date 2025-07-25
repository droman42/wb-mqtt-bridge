# SSL Support Implementation Notes

## Overview

This document outlines the implementation details of adding SSL/TLS support for LG WebOS TV connections in the WB-MQTT-Bridge project.

## Components

### 1. Certificate Extraction Tool

- Created a standalone script `extract_lg_tv_cert.py` for extracting and saving TV certificates
- The script handles:
  - Connecting to the TV using insecure SSL
  - Extracting the certificate
  - Converting to PEM format
  - Saving to a file
  - Displaying certificate details
  - Optional verification

### 2. LgTvConfig Model Updates

- Enhanced the Pydantic model with new fields:
  - `secure` (bool): Whether to use secure WebSocket connection
  - `cert_file` (str): Path to the certificate file
  - `verify_ssl` (bool): Whether to verify the SSL certificate
  - `ssl_options` (dict): Additional SSL options
- Added validation to check certificate existence

### 3. LgTv Class Enhancements

- Updated the `_connect_to_tv` method to:
  - Support secure connections using `SecureWebOSClient`
  - Handle SSL context creation with certificates
  - Provide fallback for certificate verification failures
  - Improve error reporting for SSL issues
- Added certificate management methods:
  - `extract_certificate`: Extracts and saves the TV's certificate
  - `verify_certificate`: Verifies if a certificate matches the TV

### 4. New API Actions

- Added two new actions to the `execute_action` method:
  - `extract_certificate`: For certificate extraction
  - `verify_certificate`: For certificate validation

### 5. Documentation

- Updated README.md with SSL support information
- Created implementation notes (this document)

## Technical Details

### SSL Verification Process

The SSL connection process follows these steps:

1. Check if secure mode is enabled
2. If certificate validation is requested, load the certificate
3. Create an SSL context with the certificate
4. Attempt connection with verification
5. If verification fails and fallback is allowed, retry without verification
6. On successful connection, initialize controls and update TV state

### Certificate Management

The certificate extraction process:
1. Creates an SSL context without verification
2. Connects to the TV's secure WebSocket port (3001)
3. Retrieves the certificate in binary form
4. Converts to PEM format using pyOpenSSL
5. Saves to specified file

Certificate verification:
1. Loads the stored certificate
2. Calculates its fingerprint
3. Gets the current certificate from the TV
4. Compares fingerprints
5. Reports if they match or not

## Dependencies

- Added `pyOpenSSL>=23.2.0` to pyproject.toml dependencies for certificate handling
- Relies on the updated `asyncwebostv` library that includes `SecureWebOSClient`

## Compatibility Notes

- The code handles missing `SecureWebOSClient` gracefully for linting
- Provides configuration options to enable/disable security features
- Includes fallback mechanisms when certificate verification fails 