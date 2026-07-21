/** Lifecycle states for an asynchronous job. Mirrors the Python `JobStatus`. */
export enum JobStatus {
  Pending = "pending",
  Running = "running",
  Succeeded = "succeeded",
  Failed = "failed",
  Retrying = "retrying",
  DeadLetter = "dead_letter",
}

/**
 * Ordered stages of the AI video production pipeline. Kept in sync with the
 * Python `ContentStage` enum — one source of truth per language.
 */
export enum ContentStage {
  Research = "research",
  Idea = "idea",
  Outline = "outline",
  Script = "script",
  FactCheck = "fact_check",
  Storyboard = "storyboard",
  ScenePlanning = "scene_planning",
  ImageGeneration = "image_generation",
  VideoGeneration = "video_generation",
  VoiceGeneration = "voice_generation",
  Editing = "editing",
  Captions = "captions",
  Thumbnail = "thumbnail",
  Seo = "seo",
  Publishing = "publishing",
  Analytics = "analytics",
  Learning = "learning",
}
