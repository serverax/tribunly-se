import { Controller, Get } from '@nestjs/common';
import { loadConfig } from './core/config';
import { GraphService } from './db/graph.service';
import { PostgresService } from './db/postgres.service';
import { RedisService } from './db/redis.service';
import { LlmRouter } from './llm/llm.router';

@Controller('health')
export class HealthController {
  private readonly cfg = loadConfig();

  constructor(
    private readonly postgres: PostgresService,
    private readonly redis: RedisService,
    private readonly llm: LlmRouter,
    private readonly graph: GraphService,
  ) {}

  @Get()
  async health() {
    const [dbOk, redisOk, ollamaOk] = await Promise.all([
      this.postgres.healthCheck(),
      this.redis.ping(),
      this.llm.pingOllama(),
    ]);

    const status = dbOk && redisOk ? 'ok' : 'degraded';
    return {
      status,
      service: 'lawapp-control-plane',
      version: 'nestjs-v1',
      checks: {
        postgres: dbOk,
        redis: redisOk,
        ollama: ollamaOk,
        neo4j_enabled: this.cfg.NEO4J_ENABLED,
        graph_adapter: this.cfg.NEO4J_ENABLED ? 'neo4j_optional_fallback_postgres' : 'postgres',
        external_llm_allowed: this.cfg.ALLOW_EXTERNAL_LLM,
        lawapp_api_url: this.cfg.LAWAPP_API_URL,
      },
    };
  }
}
