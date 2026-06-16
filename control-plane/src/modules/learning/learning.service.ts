import { Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { Queue } from 'bullmq';
import { loadConfig } from '../../core/config';
import { RedisService } from '../../db/redis.service';

export type LearningProposal = {
  proposal_id: string;
  source: string;
  module?: string;
  payload: Record<string, unknown>;
  created_at: string;
};

@Injectable()
export class LearningService implements OnModuleDestroy {
  private readonly logger = new Logger(LearningService.name);
  private readonly cfg = loadConfig();
  private queue: Queue | null = null;

  constructor(private readonly redis: RedisService) {}

  private bullConnection(): { host: string; port: number; password?: string } {
    const url = new URL(this.cfg.REDIS_URL);
    return {
      host: url.hostname,
      port: Number(url.port || 6379),
      password: url.password || undefined,
    };
  }

  private async getQueue(): Promise<Queue> {
    if (!this.queue) {
      this.queue = new Queue(this.cfg.LEARNING_QUEUE_NAME, {
        connection: this.bullConnection(),
      });
    }
    return this.queue;
  }

  async enqueueProposal(proposal: LearningProposal): Promise<string> {
    const q = await this.getQueue();
    const job = await q.add('ingestion_proposal', proposal, {
      removeOnComplete: 100,
      removeOnFail: 50,
    });
    this.logger.log(`Queued learning proposal ${proposal.proposal_id} as job ${job.id}`);
    return String(job.id);
  }

  async onModuleDestroy(): Promise<void> {
    await this.queue?.close();
  }
}
