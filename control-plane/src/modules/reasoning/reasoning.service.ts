import { Injectable, Logger } from '@nestjs/common';
import { loadConfig } from '../../core/config';
import { GovernedAssessment, ProcessRequest } from '../../core/types';
import { LlmRouter } from '../../llm/llm.router';

@Injectable()
export class ReasoningService {
  private readonly logger = new Logger(ReasoningService.name);
  private readonly cfg = loadConfig();

  constructor(private readonly llmRouter: LlmRouter) {}

  /**
   * Proxy legal reasoning to Python monolith /assess (never raw OpenAI for legal answers).
   */
  async assess(
    request: ProcessRequest,
    options?: { headers?: Record<string, string>; language?: string },
  ): Promise<GovernedAssessment> {
    const route = this.llmRouter.routeForLegalAnswer();
    this.logger.debug(`Reasoning route: ${route.provider} (${route.reason})`);

    const facts =
      typeof request.facts === 'string'
        ? { narrative: request.facts }
        : (request.facts ?? {});

    const query =
      request.query ??
      `Assess ${request.claim_type.replace(/_/g, ' ')} given the supplied facts.`;

    const payload = {
      query,
      facts,
      jurisdiction: request.jurisdiction ?? 'EW',
      use_model: request.use_model ?? false,
      claim_type: request.claim_type,
      case_id: request.case_id,
      user_id: request.user_id,
      language: options?.language,
    };

    const assessUrl = `${this.cfg.LAWAPP_API_URL.replace(/\/$/, '')}/assess`;
    const res = await fetch(assessUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers ?? {}),
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(120_000),
    });

    if (!res.ok) {
      const text = await res.text();
      this.logger.error(`Brain /assess failed: ${res.status} ${text.slice(0, 500)}`);
      return {
        status: 'error',
        message: `Brain assess failed with HTTP ${res.status}`,
      };
    }

    return (await res.json()) as GovernedAssessment;
  }
}
