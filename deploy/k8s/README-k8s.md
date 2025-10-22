# Kubernetes Deployment Guide

This guide explains how to deploy the Distributed Chat System on Kubernetes.

## Prerequisites

- Kubernetes cluster (minikube, kind, or cloud provider)
- kubectl configured
- Docker image built and available

## Building the Docker Image

If using a local cluster (minikube/kind), build the image:

```bash
# Navigate to project root
cd /path/to/CSEN317-Distributed-Systems

# Build the Docker image
docker build -t distributed-chat:latest -f deploy/Dockerfile .

# For minikube, load the image
minikube image load distributed-chat:latest

# For kind, load the image
kind load docker-image distributed-chat:latest
```

## Deploying to Kubernetes

### 1. Apply ConfigMap (optional, configs are generated in pods)

```bash
kubectl apply -f deploy/k8s/configmap.yaml
```

### 2. Deploy StatefulSet and Services

```bash
kubectl apply -f deploy/k8s/service.yaml
kubectl apply -f deploy/k8s/deployment.yaml
```

### 3. Verify Deployment

```bash
# Check pods
kubectl get pods -l app=chat-node

# Check services
kubectl get svc

# Check logs
kubectl logs chat-node-0
kubectl logs chat-node-1
kubectl logs chat-node-2
```

## Architecture in Kubernetes

The deployment uses:

- **StatefulSet**: Provides stable network identities (chat-node-0, chat-node-1, chat-node-2)
- **Headless Service**: Enables direct pod-to-pod communication via DNS
- **PersistentVolumeClaims**: Each pod gets its own storage for message logs

### DNS Names

Pods can reach each other via:
- `chat-node-0.chat-service.default.svc.cluster.local:5001`
- `chat-node-1.chat-service.default.svc.cluster.local:5001`
- `chat-node-2.chat-service.default.svc.cluster.local:5001`

## Testing the Deployment

### 1. Connect to a Pod

```bash
kubectl exec -it chat-node-0 -- /bin/bash
```

### 2. Send Messages (from within a pod)

```bash
# Install in pod if needed, or use client from local machine
python -m src.client_tui --host localhost --port 5001
```

### 3. Test Leader Election

Kill the leader pod and watch election:

```bash
# Find the leader from logs
kubectl logs chat-node-0 | grep LEADER
kubectl logs chat-node-1 | grep LEADER
kubectl logs chat-node-2 | grep LEADER

# Delete the leader pod
kubectl delete pod chat-node-2

# Watch new election happen
kubectl logs -f chat-node-0
```

## Scaling

To change the number of replicas:

```bash
kubectl scale statefulset chat-node --replicas=5
```

**Note**: You'll need to update the seed_nodes configuration to include the new pods.

## Port Forwarding for Local Access

To access nodes from your local machine:

```bash
# Forward node 1
kubectl port-forward chat-node-0 5001:5001

# Forward node 2
kubectl port-forward chat-node-1 5002:5001

# Forward node 3
kubectl port-forward chat-node-2 5003:5001
```

Then connect with the client:

```bash
python -m src.client_tui --host 127.0.0.1 --port 5001
```

## Monitoring

### View Logs

```bash
# All pods
kubectl logs -l app=chat-node --tail=50 -f

# Specific pod
kubectl logs chat-node-0 -f
```

### Pod Status

```bash
kubectl get pods -l app=chat-node -o wide
```

### Events

```bash
kubectl get events --sort-by='.lastTimestamp'
```

## Cleanup

Remove all resources:

```bash
kubectl delete statefulset chat-node
kubectl delete service chat-service chat-node-lb
kubectl delete configmap chat-node-config
kubectl delete pvc -l app=chat-node
```

## Troubleshooting

### Pods Not Starting

```bash
kubectl describe pod chat-node-0
kubectl logs chat-node-0
```

### Network Issues

Check if pods can reach each other:

```bash
kubectl exec chat-node-0 -- ping chat-node-1.chat-service.default.svc.cluster.local
```

### PVC Issues

Check persistent volume claims:

```bash
kubectl get pvc
kubectl describe pvc data-chat-node-0
```

## Production Considerations

For production deployments, consider:

1. **Resource Limits**: Adjust CPU/memory based on load
2. **Storage**: Use production-grade storage class
3. **High Availability**: Deploy across multiple availability zones
4. **Monitoring**: Add Prometheus metrics and Grafana dashboards
5. **Security**: Enable TLS, network policies, and RBAC
6. **Backup**: Implement PVC backup strategy
7. **Ingress**: Add ingress controller for external access

