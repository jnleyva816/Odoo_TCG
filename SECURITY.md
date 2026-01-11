# Security Policy

## Reporting a Vulnerability

We take the security of our TCG Inventory Management System seriously. If you discover a security vulnerability, please report it to us promptly.

### How to Report

**Email**: joshleyva816@gmail.com

Please include:
- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact
- Any suggested fixes (if available)

### What to Expect

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity, typically 30-90 days

### Security Best Practices

When deploying this application:

1. **Always change default credentials** in `.env` file
2. **Generate strong JWT secret**: `openssl rand -hex 32`
3. **Use HTTPS** in production (configure reverse proxy)
4. **Keep dependencies updated**: Run `pip-audit` and `npm audit`
5. **Enable rate limiting** (already configured)
6. **Review security headers** in middleware
7. **Set up firewall rules** on your server
8. **Regular backups** of database and config

### Known Security Features

- ✅ JWT-based authentication with expiration
- ✅ Password hashing with bcrypt
- ✅ Rate limiting on API endpoints
- ✅ Security headers (HSTS, CSP, X-Frame-Options, etc.)
- ✅ Input validation and sanitization
- ✅ CORS configuration
- ✅ Request ID tracing
- ✅ Structured logging for audit trails

### Security Headers

The application includes the following security headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security` (production only)
- `Content-Security-Policy`
- `Referrer-Policy`
- `Permissions-Policy`

### Rate Limiting

Default rate limits:
- 60 requests per minute per IP
- 10 requests per 5 seconds (burst protection)

### Responsible Disclosure

We follow responsible disclosure practices:

1. **Report privately** - Don't publish vulnerabilities publicly until fixed
2. **Give us time** - Allow reasonable time for fixes before disclosure
3. **Coordinate disclosure** - We'll work with you on disclosure timing

### Out of Scope

The following are considered out of scope:

- Denial of Service attacks
- Social engineering attacks
- Physical attacks on servers
- Issues in third-party dependencies (report to upstream)

## Security Updates

Security updates are released as soon as possible after discovery. We recommend:

- Subscribe to GitHub releases
- Monitor the repository for security advisories
- Keep your deployment up to date

## Questions?

For security questions or concerns, contact: joshleyva816@gmail.com
