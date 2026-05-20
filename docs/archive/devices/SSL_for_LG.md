# Coding Specification: AsyncWebOSTV Secure Connection Support

## 1. AsyncWebOSTV Library Modifications

Completed in `asyncwebostv` library. You need to do a deep analysis of the new code.

## 2. Certificate Extraction Tool

Create a standalone script `extract_lg_tv_cert.py` to extract and save certificates from LG TVs.

### Command Line Arguments

```
usage: extract_lg_tv_cert.py [-h] [--port PORT] [--output OUTPUT] [--force] [--verify] hostname

Extract SSL certificate from LG WebOS TV

positional arguments:
  hostname         TV hostname or IP address

optional arguments:
  -h, --help       show this help message and exit
  --port PORT      WebSocket port (default: 3001)
  --output OUTPUT  Output certificate file (default: hostname_cert.pem)
  --force          Overwrite existing certificate file
  --verify         Verify certificate after extraction
  --verbose        Enable verbose output
```

### Implementation Details

1. **Main functionality**:
   - Connect to the TV using SSL without verification
   - Extract the certificate
   - Save to specified file
   - Optionally verify the certificate

2. **Certificate information display**:
   - Display certificate details (issuer, validity dates, fingerprint)
   - Provide hints for configuration

3. **Error handling**:
   - Handle connection issues
   - Check if TV is reachable before attempting SSL connection
   - Validate certificate format

## 3. LgTv Class Modifications

Update the `LgTv` class to support secure connections with certificate validation.

### Config Parameters

Add support for the following config parameters in the `tv` section:
- `secure`: (bool) Whether to use secure WebSocket connection
- `cert_file`: (str) Path to the certificate file
- `verify_ssl`: (bool) Whether to verify the SSL certificate
- `ssl_options`: (dict) Additional SSL options

### Pydantic Model Updates

Update the `LgTvConfig` Pydantic model:

```python
class LgTvConfig(BaseModel):
    """Configuration for LG TV device"""
    ip_address: str
    mac_address: Optional[str] = None
    client_key: Optional[str] = None
    secure: bool = True
    cert_file: Optional[str] = None
    verify_ssl: bool = True
    ssl_options: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = 15
    
    @validator('cert_file')
    def validate_cert_file(cls, v, values):
        """Validate that cert_file exists if secure=True and verify_ssl=True"""
        if values.get('secure', True) and values.get('verify_ssl', True) and v:
            if not os.path.exists(v):
                raise ValueError(f"Certificate file {v} does not exist")
        return v
```

### Connection Logic Updates

Modify the `_connect_to_tv` method:

```python
async def _connect_to_tv(self) -> bool:
    """Connect to the TV using the configured parameters."""
    try:
        # Check configuration
        # ...

        # Use secure WebSocket mode from config
        secure_mode = self.tv_config.secure
        
        # Get certificate file path if provided
        cert_file = self.tv_config.cert_file
        
        # Determine if SSL should be verified
        verify_ssl = self.tv_config.verify_ssl
        
        # Get any additional SSL options
        ssl_options = self.tv_config.ssl_options or {}
        
        # Create a new TV client with appropriate security settings
        from asyncwebostv.connection import SecureWebOSClient
        self.client = SecureWebOSClient(
            ip,
            secure=secure_mode,
            client_key=self.client_key,
            cert_file=cert_file,
            verify_ssl=verify_ssl,
            ssl_options=ssl_options
        )
        
        # First connection attempt
        connection_success = False
        try:
            logger.info(f"Attempting to connect to TV at {ip}...")
            await self.client.connect()
            connection_success = True
        except Exception as e:
            logger.warning(f"Initial connection attempt failed: {str(e)}")
            
            # Handle Wake-on-LAN and retry...
            # ...
```

### Certificate Management Methods

Add methods to help with certificate management:

1. `async def extract_certificate(self, output_file=None)`
   - Extract certificate from the TV
   - Save to the configured or specified path
   - Update configuration

2. `async def verify_certificate(self)`
   - Check if current certificate matches the one on the TV
   - Report if certificate needs refreshing

### Error Handling and Recovery

Enhance error handling for SSL-related issues:

1. Better error messages for common SSL problems
2. Hints for certificate issues
3. Automatic fallback to non-secure mode with warning
4. Logging of all SSL-related events

## Additional Considerations

### Testing Strategy

1. Unit tests for the SecureWebOSClient class
2. Integration tests with mock SSL certificates
3. End-to-end test script to verify full workflow

### Documentation

1. Update documentation with examples for secure connection
2. Add section on certificate management
3. Document common issues and solutions
4. Create example configurations

### Future Extensions

1. Support for certificate auto-renewal
2. Certificate pinning for enhanced security
3. Support for custom CA certificates
4. Support for certificate verification callback

This specification provides a comprehensive approach to adding secure connection support to the AsyncWebOSTV library and the WB-MQTT-Bridge project, with flexibility for different security requirements. 