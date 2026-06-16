import { Injectable } from '@nestjs/common';
import { RedisService } from '../../db/redis.service';

@Injectable()
export class MemoryService {
  constructor(private readonly redis: RedisService) {}

  async cacheGet(key: string): Promise<string | null> {
    await this.redis.connect();
    return this.redis.getClient().get(key);
  }

  async cacheSet(key: string, value: string, ttlSeconds = 300): Promise<void> {
    await this.redis.connect();
    await this.redis.getClient().set(key, value, 'EX', ttlSeconds);
  }

  async rememberProcess(traceId: string, payload: string): Promise<void> {
    await this.cacheSet(`cp:process:${traceId}`, payload, 3600);
  }
}
