import { Logger } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { loadConfig } from './core/config';

async function bootstrap() {
  const cfg = loadConfig();
  const app = await NestFactory.create(AppModule, { logger: ['log', 'warn', 'error'] });
  app.setGlobalPrefix('api');
  await app.listen(cfg.PORT, '0.0.0.0');
  Logger.log(`LawApp control-plane listening on :${cfg.PORT}/api`, 'Bootstrap');
}

bootstrap();
