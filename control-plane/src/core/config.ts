import { z } from 'zod';

const boolFromEnv = z
  .union([z.string(), z.boolean()])
  .optional()
  .transform((v) => {
    if (typeof v === 'boolean') return v;
    if (!v) return false;
    return ['1', 'true', 'yes', 'on'].includes(v.toLowerCase());
  });

export const envSchema = z.object({
  NODE_ENV: z.string().default('development'),
  PORT: z.coerce.number().default(3001),
  DATABASE_URL: z.string().optional(),
  POSTGRES_HOST: z.string().default('db'),
  POSTGRES_PORT: z.coerce.number().default(5432),
  POSTGRES_DB: z.string().default('lawapp'),
  POSTGRES_USER: z.string().default('lawapp'),
  POSTGRES_PASSWORD: z.string().optional(),
  REDIS_URL: z.string().default('redis://redis:6379'),
  LAWAPP_API_URL: z.string().default('http://backend:8000'),
  GRAPH_RAG_SERVICE_URL: z.string().default('http://lawapp-graph-rag-service:8018'),
  OLLAMA_URL: z.string().default('http://host.docker.internal:11434'),
  OLLAMA_MODEL: z.string().default('qwen2.5:3b-instruct-q6_K'),
  ALLOW_EXTERNAL_LLM: boolFromEnv.default(false),
  NEO4J_ENABLED: boolFromEnv.default(false),
  NEO4J_URI: z.string().optional(),
  NEO4J_USER: z.string().optional(),
  NEO4J_PASSWORD: z.string().optional(),
  LEARNING_QUEUE_NAME: z.string().default('lawapp:learning:proposals'),
  INGESTION_QUEUE_NAME: z.string().default('lawapp:ingestion:jobs'),
});

export type AppConfig = z.infer<typeof envSchema>;

export function resolveDatabaseUrl(cfg: AppConfig): string {
  if (cfg.DATABASE_URL) return cfg.DATABASE_URL;
  if (!cfg.POSTGRES_PASSWORD) {
    throw new Error('POSTGRES_PASSWORD or DATABASE_URL is required');
  }
  const user = encodeURIComponent(cfg.POSTGRES_USER);
  const pass = encodeURIComponent(cfg.POSTGRES_PASSWORD);
  return `postgresql://${user}:${pass}@${cfg.POSTGRES_HOST}:${cfg.POSTGRES_PORT}/${cfg.POSTGRES_DB}`;
}

export function loadConfig(): AppConfig {
  const parsed = envSchema.safeParse(process.env);
  if (!parsed.success) {
    const msg = parsed.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ');
    throw new Error(`Invalid control-plane config: ${msg}`);
  }
  return parsed.data;
}
