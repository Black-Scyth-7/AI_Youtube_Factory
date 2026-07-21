/**
 * Public (browser-safe) environment validation for Next.js apps.
 *
 * Only `NEXT_PUBLIC_*` variables are validated here — they are the values that
 * are safe to expose to the client. Validation fails fast at build/startup so a
 * misconfigured deployment never ships with a missing API URL.
 */
import { z } from "zod";

const publicEnvSchema = z.object({
  NEXT_PUBLIC_API_URL: z.string().url().default("http://localhost:8000"),
  NEXT_PUBLIC_APP_ENV: z
    .enum(["local", "development", "staging", "production"])
    .default("local"),
});

export type PublicEnv = z.infer<typeof publicEnvSchema>;

/** Parse and validate the public environment. Throws on invalid config. */
export function loadPublicEnv(
  source: Record<string, string | undefined> = process.env,
): PublicEnv {
  const parsed = publicEnvSchema.safeParse(source);
  if (!parsed.success) {
    throw new Error(
      `Invalid public environment configuration: ${parsed.error.message}`,
    );
  }
  return parsed.data;
}
