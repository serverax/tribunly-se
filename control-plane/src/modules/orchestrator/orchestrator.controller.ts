import { BadRequestException, Body, Controller, Post } from '@nestjs/common';
import { processRequestSchema } from '../../core/types';
import { OrchestratorService } from './orchestrator.service';

@Controller('process')
export class OrchestratorController {
  constructor(private readonly orchestrator: OrchestratorService) {}

  @Post()
  async process(@Body() body: unknown) {
    const parsed = processRequestSchema.safeParse(body);
    if (!parsed.success) {
      throw new BadRequestException({
        message: 'Invalid process request',
        issues: parsed.error.issues,
      });
    }
    return this.orchestrator.process(parsed.data);
  }
}
