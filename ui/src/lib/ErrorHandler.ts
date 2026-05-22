export enum ErrorType {
  API_CONNECTION = 'api_connection',
  API_VALIDATION = 'api_validation',
  DEVICE_CLASS_UNSUPPORTED = 'device_class_unsupported',
  GENERATION_FAILURE = 'generation_failure',
  FILE_WRITE_ERROR = 'file_write_error',
  TEMPLATE_ERROR = 'template_error',
  VALIDATION_ERROR = 'validation_error'
}

export interface ErrorContext {
  deviceId?: string;
  deviceClass?: string;
  operation: string;
  timestamp: Date;
  additionalInfo?: Record<string, any>;
}

export interface RecoveryResult {
  success: boolean;
  action: 'retry' | 'skip' | 'abort' | 'continue';
  message: string;
  retryAfter?: number;
  manualSteps?: string[];
  recoveredData?: any;
}

export class ErrorHandler {
  private errorCounts = new Map<string, number>();
  private maxRetries = 3;
  
  handleError(error: Error, context: ErrorContext): RecoveryResult {
    const errorType = this.classifyError(error, context);
    const errorKey = `${context.deviceId || 'unknown'}_${errorType}`;
    
    // Track error counts
    const currentCount = this.errorCounts.get(errorKey) || 0;
    this.errorCounts.set(errorKey, currentCount + 1);
    
    console.error(`🚨 Error [${errorType}] in ${context.operation}:`, {
      error: error.message,
      context,
      attemptNumber: currentCount + 1
    });
    
    switch (errorType) {
      case ErrorType.API_CONNECTION:
        return this.handleApiConnectionError(error, context, currentCount);
      case ErrorType.DEVICE_CLASS_UNSUPPORTED:
        return this.handleUnsupportedDeviceClass(error, context);
      case ErrorType.GENERATION_FAILURE:
        return this.handleGenerationFailure(error, context, currentCount);
      case ErrorType.FILE_WRITE_ERROR:
        return this.handleFileWriteError(error, context, currentCount);
      case ErrorType.TEMPLATE_ERROR:
        return this.handleTemplateError(error, context);
      default:
        return this.handleGenericError(error, context, currentCount);
    }
  }
  
  private classifyError(error: Error, context: ErrorContext): ErrorType {
    const message = error.message.toLowerCase();
    
    if (message.includes('fetch') || message.includes('network') || message.includes('connection')) {
      return ErrorType.API_CONNECTION;
    }
    
    if (message.includes('unsupported device class')) {
      return ErrorType.DEVICE_CLASS_UNSUPPORTED;
    }
    
    if (message.includes('template') || message.includes('generation')) {
      return ErrorType.TEMPLATE_ERROR;
    }
    
    if (message.includes('write') || message.includes('enoent') || message.includes('permission')) {
      return ErrorType.FILE_WRITE_ERROR;
    }
    
    if (message.includes('validation') || message.includes('invalid')) {
      return ErrorType.VALIDATION_ERROR;
    }
    
    return ErrorType.GENERATION_FAILURE;
  }
  
  private handleApiConnectionError(error: Error, context: ErrorContext, attemptCount: number): RecoveryResult {
    if (attemptCount >= this.maxRetries) {
      return {
        success: false,
        action: 'abort',
        message: `API connection failed after ${this.maxRetries} attempts: ${error.message}`,
        manualSteps: [
          'Check if backend is running at the configured URL',
          'Verify network connectivity',
          'Check firewall settings',
          'Try using --api-base-url with correct URL'
        ]
      };
    }
    
    return {
      success: false,
      action: 'retry',
      message: `API connection failed (attempt ${attemptCount + 1}/${this.maxRetries}): ${error.message}`,
      retryAfter: Math.pow(2, attemptCount) * 1000, // Exponential backoff
      manualSteps: ['Checking backend connectivity...']
    };
  }
  
  private handleUnsupportedDeviceClass(error: Error, context: ErrorContext): RecoveryResult {
    return {
      success: false,
      action: 'skip',
      message: `Device class not supported: ${context.deviceClass}`,
      manualSteps: [
        'This device class is not yet implemented in Phase 2',
        'Currently supported: WirenboardIRDevice, LgTv, EMotivaXMC2, BroadlinkKitchenHood, AppleTVDevice',
        'The device will be skipped for now'
      ]
    };
  }
  
  private handleGenerationFailure(error: Error, context: ErrorContext, attemptCount: number): RecoveryResult {
    if (attemptCount >= this.maxRetries) {
      return {
        success: false,
        action: 'skip',
        message: `Generation failed permanently for ${context.deviceId}: ${error.message}`,
        manualSteps: [
          'Check device configuration format',
          'Verify all required fields are present',
          'Try with a simpler device configuration first'
        ]
      };
    }
    
    return {
      success: false,
      action: 'retry',
      message: `Generation failed (attempt ${attemptCount + 1}/${this.maxRetries}): ${error.message}`,
      retryAfter: 1000,
      manualSteps: ['Retrying generation with basic configuration...']
    };
  }
  
  private handleFileWriteError(error: Error, context: ErrorContext, attemptCount: number): RecoveryResult {
    return {
      success: false,
      action: 'abort',
      message: `File write error: ${error.message}`,
      manualSteps: [
        'Check write permissions for output directory',
        'Ensure sufficient disk space',
        'Verify output directory exists and is writable'
      ]
    };
  }
  
  private handleTemplateError(error: Error, context: ErrorContext): RecoveryResult {
    return {
      success: false,
      action: 'skip',
      message: `Template error for ${context.deviceId}: ${error.message}`,
      manualSteps: [
        'Device configuration may have unexpected structure',
        'Check for missing required fields',
        'Device will be skipped'
      ]
    };
  }
  
  private handleGenericError(error: Error, context: ErrorContext, attemptCount: number): RecoveryResult {
    if (attemptCount >= this.maxRetries) {
      return {
        success: false,
        action: 'skip',
        message: `Unknown error after ${this.maxRetries} attempts: ${error.message}`,
        manualSteps: [
          'Check logs for more details',
          'Try with a different device',
          'Report this issue if it persists'
        ]
      };
    }
    
    return {
      success: false,
      action: 'retry',
      message: `Unknown error (attempt ${attemptCount + 1}/${this.maxRetries}): ${error.message}`,
      retryAfter: 2000,
      manualSteps: ['Retrying operation...']
    };
  }
  
  resetErrorCount(deviceId: string): void {
    Array.from(this.errorCounts.keys())
      .filter(key => key.startsWith(deviceId))
      .forEach(key => this.errorCounts.delete(key));
  }
  
  getErrorStats(): Record<string, number> {
    const stats: Record<string, number> = {};
    this.errorCounts.forEach((count, key) => {
      const [, errorType] = key.split('_');
      stats[errorType] = (stats[errorType] || 0) + count;
    });
    return stats;
  }
} 