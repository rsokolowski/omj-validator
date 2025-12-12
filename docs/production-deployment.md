# Production Deployment Guide

This guide covers deploying OMJ Validator to a GCP Compute Engine VM with Docker Compose and Nginx.

## Architecture Overview

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  GCP VM (omj-validator)                             │
│                                                     │
│  ┌─────────────────┐                               │
│  │ Nginx           │ :443 (HTTPS)                  │
│  │ (reverse proxy) │ :80 (redirect to HTTPS)       │
│  └────────┬────────┘                               │
│           │                                         │
│           ├──────────────────┐                     │
│           ▼                  ▼                     │
│  ┌────────────────┐  ┌────────────────┐           │
│  │ Frontend       │  │ API            │           │
│  │ (Next.js)      │  │ (FastAPI)      │           │
│  │ :3100          │  │ :8100          │           │
│  └────────────────┘  └───────┬────────┘           │
│                              │                     │
│                              ▼                     │
│                      ┌────────────────┐           │
│                      │ PostgreSQL     │           │
│                      │ (internal)     │           │
│                      └────────────────┘           │
│                                                     │
│  Data: ~/omj-validator/data/                       │
│    ├── postgres/    (database files)               │
│    └── uploads/     (user images)                  │
└─────────────────────────────────────────────────────┘
```

**Domain**: https://omj-validator.duckdns.org (DuckDNS dynamic DNS)

## Prerequisites

- GCP account with Compute Engine API enabled
- Domain pointing to VM's static IP (DuckDNS or similar)
- Google OAuth credentials configured for the domain

## VM Setup (One-Time)

### 1. Create VM

```bash
# Create VM with static IP
gcloud compute instances create omj-validator \
  --zone=europe-west1-b \
  --machine-type=e2-small \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=20GB

# Reserve static IP
gcloud compute addresses create omj-validator-ip --region=europe-west1
gcloud compute instances add-access-config omj-validator \
  --access-config-name="external-nat" \
  --address=$(gcloud compute addresses describe omj-validator-ip --region=europe-west1 --format='get(address)')
```

### 2. Configure Firewall

```bash
# Allow HTTP/HTTPS traffic
gcloud compute firewall-rules create allow-http --allow tcp:80
gcloud compute firewall-rules create allow-https --allow tcp:443
```

### 3. Install Dependencies

```bash
# SSH to VM
gcloud compute ssh omj-validator

# Install Docker
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker  # Apply group change

# Install Nginx + Certbot
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 4. Clone and Configure

```bash
# Clone repo
git clone https://github.com/rsokolowski/omj-validator.git
cd omj-validator

# Create production env file
cp .env.prod.example .env.prod

# Edit with production values
nano .env.prod
```

Required `.env.prod` variables:
```bash
POSTGRES_PASSWORD=<secure-password>
SESSION_SECRET_KEY=<generate-with: openssl rand -hex 32>
GOOGLE_CLIENT_ID=<from-google-console>
GOOGLE_CLIENT_SECRET=<from-google-console>
GEMINI_API_KEY=<from-google-ai-studio>
ALLOWED_EMAILS=user1@gmail.com,user2@gmail.com
FRONTEND_URL=https://omj-validator.duckdns.org
```

### 5. Setup Nginx with SSL

```bash
# Copy nginx config
sudo cp nginx.conf.example /etc/nginx/sites-available/omj-validator
sudo ln -s /etc/nginx/sites-available/omj-validator /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default site

# Test and reload
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate (after DNS is pointing to VM)
sudo certbot --nginx -d omj-validator.duckdns.org

# Certbot auto-renewal is configured automatically
```

### 6. Start Services

```bash
cd ~/omj-validator
docker compose -f docker-compose.prod.yml --env-file .env.prod pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## Deployment (Updates)

Images are built locally and pushed to GitHub Container Registry (`ghcr.io`), then pulled on the VM.

### One-Time Setup (Local Machine)

```bash
# 1. Create GitHub Personal Access Token (PAT)
#    Go to https://github.com/settings/tokens
#    Create token with 'write:packages' scope

# 2. Login to GitHub Container Registry
echo YOUR_PAT | docker login ghcr.io -u YOUR_USERNAME --password-stdin
```

### Deploy from Local Machine

```bash
# Build images locally and push to registry
./build-and-push.sh

# Deploy to VM (pulls images from ghcr.io)
./deploy.sh

# Or both in one command
./build-and-push.sh && ./deploy.sh
```

### Deploy Script Options

```bash
./deploy.sh                  # Pull latest and restart all services
./deploy.sh --api            # Deploy only API
./deploy.sh --frontend       # Deploy only frontend
./deploy.sh --logs api       # View API logs
./deploy.sh --status         # Check container status
./deploy.sh --ssh            # SSH into VM
```

### Build Script Options

```bash
./build-and-push.sh                  # Build and push both images
./build-and-push.sh --api            # Build and push API only
./build-and-push.sh --frontend       # Build and push frontend only
./build-and-push.sh --tag v1.0.0     # Use specific tag
./build-and-push.sh --no-push        # Build only, don't push
```

## Operations

### View Logs

```bash
# API logs (most useful for debugging)
sudo docker logs omj-api --tail=100 -f

# Frontend logs
sudo docker logs omj-frontend --tail=50 -f

# Database logs
sudo docker logs omj-db --tail=50

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Service Management

```bash
# Check status
sudo docker compose -f docker-compose.prod.yml ps

# Restart services
sudo docker compose -f docker-compose.prod.yml restart api
sudo docker compose -f docker-compose.prod.yml restart frontend

# Stop all
sudo docker compose -f docker-compose.prod.yml down

# Stop and remove volumes (CAUTION: deletes data)
sudo docker compose -f docker-compose.prod.yml down -v
```

### Database Access

```bash
# Connect to PostgreSQL
sudo docker exec -it omj-db psql -U omj -d omj

# Useful queries
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM submissions;
SELECT * FROM submissions ORDER BY created_at DESC LIMIT 10;
```

### Backup

```bash
# Backup database
sudo docker exec omj-db pg_dump -U omj omj > backup_$(date +%Y%m%d).sql

# Backup uploads
tar -czf uploads_$(date +%Y%m%d).tar.gz data/uploads/
```

## Data Storage

All persistent data is stored in `~/omj-validator/data/` via bind mounts:

```
~/omj-validator/data/
├── postgres/                    # PostgreSQL database files
└── uploads/                     # User-submitted images
    └── {user_id}/
        └── {year}/
            └── {etap}/
                └── {task_num}/
                    └── *.jpg
```

## Docker Compose Services

Defined in `docker-compose.prod.yml`:

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| db | omj-db | internal | PostgreSQL 16, only accessible within Docker network |
| api | omj-api | 127.0.0.1:8100 | FastAPI backend with Gunicorn |
| frontend | omj-frontend | 127.0.0.1:3100 | Next.js standalone server |

## Troubleshooting

### Container won't start

```bash
# Check container logs
sudo docker logs omj-api

# Common issues:
# - Missing environment variables in .env.prod
# - Database not ready (check omj-db health)
# - Port already in use
```

### WebSocket not working

- Ensure Nginx config includes WebSocket upgrade headers
- Check API logs for session decode errors
- Verify `FRONTEND_URL` matches actual domain

### SSL certificate issues

```bash
# Renew manually
sudo certbot renew

# Check certificate status
sudo certbot certificates
```

### Database connection issues

```bash
# Check if db container is healthy
sudo docker compose -f docker-compose.prod.yml ps

# Restart database
sudo docker compose -f docker-compose.prod.yml restart db
```

## Security Notes

- All services bind to `127.0.0.1` (localhost only), exposed via Nginx
- PostgreSQL is not exposed to host, only accessible within Docker network
- SSL enforced via Nginx redirect
- Session cookies are HttpOnly and Secure
- Use strong passwords in `.env.prod`
