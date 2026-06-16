import { Injectable, Logger } from '@nestjs/common';
import { loadConfig } from '../core/config';

export type LlmRouteDecision = {
  provider: 'ollama_local' | 'python_brain' | 'external_blocked';
  model: string;
  reason: string;
};

/**
 * Local Ollama default; external LLM gated by ALLOW_EXTERNAL_LLM (owner decision).
 * Legal answers MUST go through Python Brain /assess for CitationGuard.
 */
@Injectable()
export class LlmRouter {
  private readonly logger = new Logger(LlmRouter.name);
  private readonly cfg = loadConfig();

  routeForLegalAnswer(): LlmRouteDecision {
    return {
      provider: 'python_brain',
      model: this.cfg.OLLAMA_MODEL,
      reason: 'Legal answers proxy to FastAPI /assess (CitationGuard enforced)',
    };
  }

  routeForAuxiliaryTask(task: 'summarize' | 'classify' | 'ingest'): LlmRouteDecision {
    if (this.cfg.ALLOW_EXTERNAL_LLM) {
      this.logger.warn('ALLOW_EXTERNAL_LLM=true but no external provider wired in v1');
    }
    return {
      provider: 'ollama_local',
      model: this.cfg.OLLAMA_MODEL,
      reason: `Auxiliary task ${task} uses local Ollama`,
    };
  }

  async pingOllama(): Promise<boolean> {
    try {
      const res = await fetch(`${this.cfg.OLLAMA_URL}/api/tags`, {
        signal: AbortSignal.timeout(3000),
      });
      return res.ok;
    } catch {
      return false;
    }
  }
}
