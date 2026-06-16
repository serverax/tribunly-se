import { Module } from '@nestjs/common';
import { HealthController } from './health.controller';
import { PostgresService } from './db/postgres.service';
import { RedisService } from './db/redis.service';
import { GraphService } from './db/graph.service';
import { LlmRouter } from './llm/llm.router';
import { OrchestratorController } from './modules/orchestrator/orchestrator.controller';
import { OrchestratorService } from './modules/orchestrator/orchestrator.service';
import { RetrievalService } from './modules/retrieval/retrieval.service';
import { ReasoningService } from './modules/reasoning/reasoning.service';
import { GovernanceService } from './modules/governance/governance.service';
import { MemoryService } from './modules/memory/memory.service';
import { LearningService } from './modules/learning/learning.service';
import { IngestionPipeline } from './modules/ingestion/ingestion.pipeline';

@Module({
  imports: [],
  controllers: [HealthController, OrchestratorController],
  providers: [
    PostgresService,
    RedisService,
    GraphService,
    LlmRouter,
    RetrievalService,
    ReasoningService,
    GovernanceService,
    MemoryService,
    LearningService,
    IngestionPipeline,
    OrchestratorService,
  ],
})
export class AppModule {}
