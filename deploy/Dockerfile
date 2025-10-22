# Multi-stage Dockerfile for Distributed Chat System
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --user -r requirements.txt


# Final stage
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 chatuser && \
    mkdir -p /app /data/logs && \
    chown -R chatuser:chatuser /app /data

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/chatuser/.local

# Copy application code
COPY --chown=chatuser:chatuser src/ ./src/
COPY --chown=chatuser:chatuser configs/ ./configs/

# Switch to non-root user
USER chatuser

# Add local bin to PATH
ENV PATH=/home/chatuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Expose port (will be overridden per node)
EXPOSE 5001

# Default command
CMD ["python", "-m", "src.node", "--config", "configs/node1.yml"]

