import app from './app';
import { config } from './config';

app.listen(config.port, () => {
  console.log(`[ReviewHub] Server running on port ${config.port}`);
  console.log(`[ReviewHub] Environment: ${config.nodeEnv}`);
});
