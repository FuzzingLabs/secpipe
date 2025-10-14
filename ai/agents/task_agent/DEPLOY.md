# Docker & Kubernetes Deployment

## Local Docker

Build from the repository root:

```bash
docker build -t litellm-hot-swap:latest agent_with_adk_format
```

Run the container (port 8000, inject provider keys via env file or flags):

```bash
docker run \
  -p 8000:8000 \
  --env-file agent_with_adk_format/.env \
  litellm-hot-swap:latest
```

The container serves Uvicorn on `http://localhost:8000`. Update `.env` (or pass `-e KEY=value`) before launching if you plan to hot-swap providers.

## Kubernetes (example manifest)

Use the same image, optionally pushed to a registry (`docker tag` + `docker push`). A simple Deployment/Service pair:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm-hot-swap
spec:
  replicas: 1
  selector:
    matchLabels:
      app: litellm-hot-swap
  template:
    metadata:
      labels:
        app: litellm-hot-swap
    spec:
      containers:
      - name: server
        image: <REGISTRY_URI>/litellm-hot-swap:latest
        ports:
        - containerPort: 8000
        env:
        - name: PORT
          value: "8000"
        - name: LITELLM_MODEL
          value: gemini/gemini-2.0-flash-001
        # Add provider keys as needed
        # - name: OPENAI_API_KEY
        #   valueFrom:
        #     secretKeyRef:
        #       name: litellm-secrets
        #       key: OPENAI_API_KEY
---
apiVersion: v1
kind: Service
metadata:
  name: litellm-hot-swap
spec:
  type: LoadBalancer
  selector:
    app: litellm-hot-swap
  ports:
  - port: 80
    targetPort: 8000
```

Apply with `kubectl apply -f deployment.yaml`. Provide secrets via `env` or Kubernetes Secrets.
