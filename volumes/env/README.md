# FuzzForge Environment Configuration

This directory contains environment files that are mounted into Docker containers.

## Files

- `.env.example` - Template configuration file
- `.env` - Your actual configuration (create by copying .env.example)

## Usage

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys

3. Restart Docker containers to apply changes:
   ```bash
   docker-compose restart
   ```
