from __future__ import annotations

SERVICES = [
    {"name": "api-gateway", "path": "services/api-gateway", "host_port": 8080},
    {"name": "identity-service", "path": "services/identity-service", "host_port": 8081},
    {"name": "tenant-service", "path": "services/tenant-service", "host_port": 8082},
    {"name": "device-registry-service", "path": "services/device-registry-service", "host_port": 8083},
    {"name": "usage-metering-service", "path": "services/usage-metering-service", "host_port": 8084},
    {"name": "voice-session-service", "path": "services/voice-session-service", "host_port": 8085},
    {"name": "conversation-service", "path": "services/conversation-service", "host_port": 8086},
    {"name": "speech-provider-service", "path": "services/speech-provider-service", "host_port": 8087},
    {"name": "llm-gateway-service", "path": "services/llm-gateway-service", "host_port": 8088},
    {"name": "agent-orchestrator-service", "path": "services/agent-orchestrator-service", "host_port": 8089},
    {"name": "billing-service", "path": "services/billing-service", "host_port": 8090},
    {"name": "subscription-service", "path": "services/subscription-service", "host_port": 8091},
    {"name": "notification-service", "path": "services/notification-service", "host_port": 8092},
    {"name": "skill-registry-service", "path": "services/skill-registry-service", "host_port": 8093},
]

def env_prefix(name: str) -> str:
    return "GOFTAROO_" + name.upper().replace("-", "_")
