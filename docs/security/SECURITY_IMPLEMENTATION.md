# Security Implementation Guide

## Overview

This document outlines the security mechanisms implemented in the Odoo TCG Inventory Management System and provides guidance for maintaining and improving security posture.

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Transport Security](#transport-security)
3. [Input Validation](#input-validation)
4. [Rate Limiting](#rate-limiting)
5. [Security Headers](#security-headers)
6. [Secrets Management](#secrets-management)
7. [Dependency Security](#dependency-security)
8. [Monitoring & Alerting](#monitoring--alerting)
9. [Incident Response](#incident-response)

---

## Authentication & Authorization

### JWT Token Management

**Current Implementation:**
- HS256 algorithm with 24-hour expiry
- Tokens issued after Odoo credential validation
- No refresh token mechanism (stateless)

**Recommended Enhancements:**
- Implement refresh token rotation (7-day expiry)
- Reduce access token lifetime to 15-60 minutes
- Add token blacklisting for logout
- Implement multi-factor authentication (TOTP)

### Password Security

**Best Practices:**
- Enforce password complexity (min 12 chars, mix of types)
- Implement password history (prevent reuse of last 5)
- Add password strength indicator in UI
- Enable account lockout after failed attempts

---

## Transport Security

### HTTPS Configuration

**Production Nginx Setup:**

```nginx
server {
    listen 443 ssl http2;
    server_name inventory.example.com;

    # TLS 1.3 preferred
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256';
    ssl_prefer_server_ciphers on;

    # Let's Encrypt certificates
    ssl_certificate /etc/letsencrypt/live/inventory.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/inventory.example.com/privkey.pem;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Input Validation

### Validator Coverage

**Implemented:** (`backend/app/utils/validators.py`)
- Email validation (RFC 5322)
- SKU format validation
- HTML sanitization (XSS prevention)
- Filename sanitization (path traversal prevention)
- Barcode validation (EAN-13, UPC-A, Code-128)

**Additional Recommendations:**
- Add SQL injection tests for Odoo queries
- Implement rate limiting on validation failures
- Log suspicious validation patterns

---

## Rate Limiting

### Current Implementation

- 1200 requests/minute (20 req/sec)
- 300-request burst protection
- Redis-backed distributed rate limiting
- Per-IP tracking with proxy support

### Enhancement: Per-User Rate Limiting

Implement additional user-based limits:
- Authenticated users: 300 req/min
- Unauthenticated users: 30 req/min
- Admin users: 1000 req/min

---

## Security Headers

### OWASP Recommended Headers

All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security` (production)
- `Content-Security-Policy`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`

### Testing

```bash
# Test with curl
curl -I https://inventory.example.com

# Use Mozilla Observatory
https://observatory.mozilla.org/
```

---

## Secrets Management

### Current Approach
- Environment variables in `.env` file
- Docker Compose secrets support
- Git-ignored sensitive files

### Production Recommendations

#### Docker Secrets

```yaml
services:
  backend:
    secrets:
      - jwt_secret_key
      - odoo_password

secrets:
  jwt_secret_key:
    external: true
```

#### HashiCorp Vault

```python
import hvac

client = hvac.Client(url='http://vault:8200')
secret = client.secrets.kv.v2.read_secret_version(path='tcg/jwt')
jwt_secret = secret['data']['data']['secret_key']
```

---

## Dependency Security

### Automated Scanning

**GitHub Actions Workflows:**
- `security-scan.yml` - Daily vulnerability scans
- Tools: pip-audit, Safety, Bandit, npm audit, Trivy

**Manual Scanning:**

```bash
# Python
pip-audit --desc
safety check
bandit -r app/ -ll

# JavaScript
npm audit --audit-level=moderate

# Containers
trivy image tcg-backend:latest
```

### Remediation Process

1. Automated detection via CI/CD
2. Triage by severity (CRITICAL/HIGH priority)
3. Update to patched version
4. Test in staging
5. Deploy to production

---

## Monitoring & Alerting

### Security Event Logging

Implemented structured logging for:
- Login attempts (success/failure)
- Rate limit violations
- Invalid token usage
- Permission denied events

### Recommended Metrics

```python
from prometheus_client import Counter

login_attempts = Counter('login_attempts_total', 'Login attempts', ['status'])
rate_limit_hits = Counter('rate_limit_hits_total', 'Rate limit violations')
```

---

## Incident Response

### Emergency Procedures

**Containment:**
```bash
# Disable service
docker compose stop backend

# Block IP
iptables -A INPUT -s <ip> -j DROP

# Rotate secrets
kubectl set env deployment/tcg-backend JWT_SECRET_KEY=$(openssl rand -hex 32)
```

**Investigation:**
- Review logs: `docker compose logs backend`
- Check Redis for suspicious activity
- Analyze request patterns

**Recovery:**
```bash
# Deploy patched version
git pull origin main
docker compose up -d --build
```

---

## OWASP Top 10 Coverage

- [x] A01 Broken Access Control
- [x] A02 Cryptographic Failures
- [x] A03 Injection
- [x] A04 Insecure Design
- [x] A05 Security Misconfiguration
- [x] A06 Vulnerable Components
- [x] A07 Authentication Failures
- [x] A08 Software & Data Integrity
- [x] A09 Logging & Monitoring
- [x] A10 SSRF

---

## Security Testing

### Automated Tests

```python
def test_security_headers(client):
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"

def test_rate_limiting(client):
    for _ in range(1300):
        client.get("/api/cards/search?q=test")
    assert response.status_code == 429
```

### Manual Testing

```bash
# OWASP ZAP
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://inventory.example.com

# Nmap
nmap -sV inventory.example.com

# Nikto
nikto -h https://inventory.example.com
```

---

## Continuous Improvement

### Review Cadence

- **Weekly:** Review security logs
- **Monthly:** Update dependencies
- **Quarterly:** Full security audit
- **Annually:** Third-party assessment

### Security Roadmap

**Q1 2026:**
- Implement MFA (TOTP)
- Add refresh token rotation
- Deploy WAF

**Q2 2026:**
- CSP with nonces
- API versioning
- IDS deployment

---

## References

- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Mozilla Web Security](https://infosec.mozilla.org/guidelines/web_security)
