# EmotivaXMC2 Midnight MQTT Flooding Bug Investigation

## Problem Description

**Issue:** MQTT command flooding occurs around midnight, but only when the EmotivaXMC2 device is powered on. The flooding includes:
- LG TV receiving spurious commands  
- Kitchen hood turning off spontaneously around midnight
- System-wide MQTT message flood with all device commands being triggered
- No commands should be triggered - user was manually controlling TV with remote

**Key Observations:**
- Only happens when EmotivaXMC2 is on
- TV + Apple TV alone runs smooth
- Kitchen hood turns off around midnight
- Service runs in Docker container with `--restart unless-stopped`
- Log directory is mounted outside container (`-v "$(pwd)/logs:/app/logs"`)
- EmotivaXMC2 becomes "stuck" during flooding: Device continues to respond to MQTT but stops updating its state

## Root Cause Analysis

✅ **Concurrency Issue in EmotivaXMC2 Device** (FIXED)
- Multiple concurrent setup() calls during MQTT floods
- Added asyncio.Lock and double-checked locking pattern
- Prevents multiple simultaneous connection attempts

✅ **MQTT Message Processing** (FIXED)
- Added retain flag checks in main MQTT client
- Added retain flag checks in MQTT sniffer
- Prevents processing of stale retained messages

## Tasks

### High Priority
1. **System-wide Concurrency Investigation**
   - Review all device classes for similar concurrency issues
   - Focus on network-connected devices first
   - Implement similar locking patterns where needed

2. **MQTT Message Processing Improvements**
   - ✅ Retain flag handling implemented
   - Add message deduplication
   - Consider rate limiting for flood protection

3. **System Resilience**
   - Add circuit breakers for device connections
   - Implement graceful degradation during high load
   - Add system-wide rate limiting

### Testing
1. **Load Testing**
   - Create test suite for concurrent command handling
   - Simulate MQTT message floods
   - Verify device state consistency under load

2. **Long-running Tests**
   - Monitor system behavior over 24+ hours
   - Focus on midnight transition period
   - Track memory and connection states

## Status
- ✅ Root cause identified
- ✅ EmotivaXMC2 concurrency fix implemented
- ✅ MQTT retain message handling implemented
- 🔄 System-wide improvements in progress 