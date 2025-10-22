# Quick Start Guide

Get the Distributed Chat System running in 5 minutes.

## Option 1: Docker Compose (Recommended)

```bash
# 1. Navigate to deploy directory
cd deploy

# 2. Start the cluster
docker compose up --build

# 3. In another terminal, connect a client
docker exec -it chat_node1 python -m src.client_tui --host chat_node2 --port 5002

# 4. Type messages and see them appear on all nodes!

# 5. Test leader failure
docker stop chat_node3  # Kill the leader
# Watch node 2 become new leader in logs

# 6. Cleanup
docker compose down -v
```

## Option 2: Local Python

```bash
# 1. Setup
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
mkdir -p data/logs

# 2. Start three nodes (in separate terminals)
python -m src.node --config configs/node1.yml
python -m src.node --config configs/node2.yml
python -m src.node --config configs/node3.yml

# 3. Connect client (in a 4th terminal)
python -m src.client_tui --host 127.0.0.1 --port 5001

# 4. Send messages!
> Hello distributed world!
```

## Option 3: Using Makefile

```bash
# Setup
make setup-dev
source venv/bin/activate
make install

# Start nodes (in separate terminals)
make run-node1
make run-node2
make run-node3

# Connect client (in another terminal)
make client

# Or use Docker
make docker-up
```

## What to Expect

When everything is running:

1. **Logs show**:
   - Nodes discovering each other
   - Election process (node 3 becomes leader)
   - Heartbeats being exchanged

2. **Client interface**:
   - Type messages and press Enter
   - Messages appear with sequence numbers: `[seq=1] node_1: Hello!`

3. **All nodes show identical order**:
   - Check all node terminals
   - Same messages, same sequence numbers

## Test Leader Failure

1. Identify leader (highest node_id, typically node 3)
2. Kill it: `Ctrl+C` (local) or `docker stop chat_node3` (Docker)
3. Watch remaining nodes elect new leader
4. Continue sending messages - ordering maintained!

## Troubleshooting

**Nodes won't connect?**
- For local: Use `127.0.0.1` instead of hostnames in configs
- For Docker: Check `docker network ls` and container names

**Port in use?**
- Change ports in config files
- Or kill existing process: `lsof -i :5001`

**Need help?**
- Check full `README.md` for detailed docs
- Run tests: `pytest tests/ -v`
- View logs carefully - they're very informative!

## Next Steps

- Read `README.md` for architecture details
- Try killing/restarting nodes
- Run the test suite
- Explore the code in `src/`
- Check `deploy/k8s/README-k8s.md` for Kubernetes deployment

Enjoy exploring distributed systems!

