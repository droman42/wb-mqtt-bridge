import { runtimeConfig } from '../config/runtime';

interface HTTPRequestDetails {
  method: string;
  url: string;
  body?: any;
}

/**
 * Formats HTTP request details for display in tooltips
 */
export function formatHTTPRequestForTooltip(details: HTTPRequestDetails): string {
  const { method, url, body } = details;
  
  let formatted = `${method} ${url}`;
  
  if (body && Object.keys(body).length > 0) {
    formatted += `\nBody: ${JSON.stringify(body, null, 2)}`;
  }
  
  return formatted;
}

/**
 * Creates HTTP request details for device actions
 */
export function createDeviceActionHTTPDetails(deviceId: string, action: string, params?: any): HTTPRequestDetails {
  const baseUrl = runtimeConfig.apiBaseUrl || '/api';
  
  return {
    method: 'POST',
    url: `${baseUrl}/devices/${deviceId}/action`,
    body: {
      action,
      params: params || {}
    }
  };
}

/**
 * Creates enhanced tooltip for device pages (action name + HTTP request)
 */
export function createDeviceTooltip(actionName: string, actionDescription: string, deviceId: string, action: string, params?: any): string {
  const displayName = actionDescription || actionName;
  const httpDetails = createDeviceActionHTTPDetails(deviceId, action, params);
  const httpFormatted = formatHTTPRequestForTooltip(httpDetails);
  
  return `${displayName}\n\n${httpFormatted}`;
}

/**
 * Creates enhanced tooltip for scenario pages (action name + device_id + HTTP request)
 */
export function createScenarioTooltip(actionName: string, actionDescription: string, targetDeviceId: string, action: string, params?: any): string {
  const displayName = actionDescription || actionName;
  const httpDetails = createDeviceActionHTTPDetails(targetDeviceId, action, params);
  const httpFormatted = formatHTTPRequestForTooltip(httpDetails);
  
  return `${displayName}\n\nTarget Device: ${targetDeviceId}\n\n${httpFormatted}`;
}

/**
 * Creates enhanced tooltip for actions with optional source device routing
 */
export function createActionTooltip(actionName: string, actionDescription: string, deviceId: string, action: string, params?: any, sourceDeviceId?: string): string {
  const isScenario = !!sourceDeviceId;
  const targetDeviceId = sourceDeviceId || deviceId;
  
  if (isScenario) {
    return createScenarioTooltip(actionName, actionDescription, targetDeviceId, action, params);
  } else {
    return createDeviceTooltip(actionName, actionDescription, targetDeviceId, action, params);
  }
} 