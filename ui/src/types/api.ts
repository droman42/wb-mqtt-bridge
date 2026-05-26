// API types — thin named aliases over the generated OpenAPI contract (openapi.gen.ts), so the
// backend schema is the single source of truth. openapi-typescript only exports `components`/`paths`,
// so this ergonomic re-export layer gives the rest of the app clean named types backed by the
// generated schemas. The hand-written duplicates were removed at the Layer-3 cutover (A8 phase 2).
// (ManualInstructions has two same-named backend models → no clean alias; it's reached transitively
// via ScenarioDefinition. The UI's own ManualInstructions lives in RemoteControlLayout.ts.)
import type { components } from './openapi.gen';

type S = components['schemas'];

export type DeviceAction = S['DeviceAction'];
export type DeviceState = S['DeviceState'];
export type CommandResponse = S['CommandResponse'];
export type RoomDefinitionResponse = S['RoomDefinitionResponse'];
export type CommandStep = S['CommandStep'];
export type ScenarioDefinition = S['ScenarioDefinition'];
export type ScenarioState = S['ScenarioState'];
export type ManualStep = S['ManualStep'];
export type ScenarioResponse = S['ScenarioResponse'];
export type SwitchScenarioRequest = S['SwitchScenarioRequest'];
export type ActionRequest = S['ActionRequest'];
export type MQTTMessage = S['MQTTMessage'];
export type MQTTPublishResponse = S['MQTTPublishResponse'];
export type MQTTBrokerConfig = S['MQTTBrokerConfig'];
export type SystemInfo = S['SystemInfo'];
export type PersistenceConfig = S['PersistenceConfig'];
export type SystemConfig = S['SystemConfig'];
export type ReloadResponse = S['ReloadResponse'];
export type PersistedStatesResponse = S['PersistedStatesResponse'];
