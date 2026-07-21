/**
 * Central feature-flag registry.
 *
 * Flags default off and are the single switchboard for progressively enabling
 * platform capabilities across environments. Later phases wire these to a remote
 * config source; Phase 01 ships static defaults.
 */
export interface FeatureFlags {
  aiPipeline: boolean;
  workflowEngine: boolean;
  pluginEcosystem: boolean;
  teamCollaboration: boolean;
  billing: boolean;
}

export const defaultFeatureFlags: FeatureFlags = {
  aiPipeline: false,
  workflowEngine: false,
  pluginEcosystem: false,
  teamCollaboration: false,
  billing: false,
};

/** Merge overrides onto the defaults (e.g. from env or remote config). */
export function resolveFeatureFlags(
  overrides: Partial<FeatureFlags> = {},
): FeatureFlags {
  return { ...defaultFeatureFlags, ...overrides };
}
