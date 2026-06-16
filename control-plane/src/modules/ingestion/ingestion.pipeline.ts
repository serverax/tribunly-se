import { Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { Queue } from 'bullmq';
import { loadConfig } from '../../core/config';
import { RedisService } from '../../db/redis.service';

export type IngestionJob = {
  job_id: string;
  source: 'legislation.gov.uk' | 'gov.uk' | 'acas.org.uk';
  path: string;
  metadata?: Record<string, unknown>;
};

@Injectable()
export class IngestionPipeline implements OnModuleDestroy {
  private readonly logger = new Logger(IngestionPipeline.name);
  private readonly cfg = loadConfig();
  private queue: Queue | null = null;

  constructor(private readonly redis: RedisService) {}

  private async getQueue(): Promise<Queue> {
    if (!this.queue) {
      await this.redis.connect();
      this.queue = new Queue(this.cfg.INGESTION_QUEUE_NAME, {
        connection: this.redis.getClient().duplicate(),
      });
    }
    return this.queue;
  }

  async scheduleUkGovIngestion(job: IngestionJob): Promise<string> {
    const q = await this.getQueue();
    const bullJob = await q.add('uk_gov_ingest', job, {
      attempts: 3,
      backoff: { type: 'exponential', delay: 5000 },
    });
    this.logger.log(`Scheduled UK gov ingestion ${job.job_id} (${job.source})`);
    return String(bullJob.id);
  }

  async onModuleDestroy(): Promise<void> {
    await this.queue?.close();
  }
}
