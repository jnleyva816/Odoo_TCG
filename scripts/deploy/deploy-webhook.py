#!/usr/bin/env python3
"""
GitHub Webhook Receiver for Auto-Deploy

This script runs on your Proxmox server and listens for GitHub push events.
When a push is detected, it pulls the latest code and redeploys.

Setup:
    1. Copy this to your Proxmox server
    2. Run: python3 deploy-webhook.py
    3. Add webhook in GitHub: Settings → Webhooks → Add webhook
       - Payload URL: http://your-proxmox-ip:9000/deploy
       - Content type: application/json
       - Secret: (set WEBHOOK_SECRET env var)
       - Events: Just the push event

Usage:
    WEBHOOK_SECRET=your-secret-here python3 deploy-webhook.py
"""

import hashlib
import hmac
import http.server
import json
import os
import socketserver
import subprocess
import threading
import time
from datetime import datetime

# Configuration
PORT = 9000
REPO_PATH = os.environ.get("REPO_PATH", "/var/lib/Odoo_TCG")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
BRANCH = os.environ.get("BRANCH", "main")

# Rate limiting: track deploy requests
_last_deploy_time = 0
_deploy_lock = threading.Lock()
DEPLOY_COOLDOWN = 30  # seconds between deploys


def log(message: str, level: str = "INFO"):
    """Log with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature."""
    if not WEBHOOK_SECRET:
        log("No WEBHOOK_SECRET set - skipping signature verification", "WARN")
        return True
    
    if not signature:
        return False
    
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


def deploy():
    """Pull latest code and redeploy."""
    global _last_deploy_time
    
    with _deploy_lock:
        now = time.time()
        if now - _last_deploy_time < DEPLOY_COOLDOWN:
            log(f"Deploy rate limited (cooldown: {DEPLOY_COOLDOWN}s)", "WARN")
            return False
        _last_deploy_time = now
    
    log("Starting deployment...")
    
    try:
        # Pull latest code
        log("Pulling latest code...")
        result = subprocess.run(
            ["git", "pull", "origin", BRANCH],
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout.strip():
            log(f"Git: {result.stdout.strip()}")
        if result.returncode != 0:
            log(f"Git pull failed: {result.stderr}", "ERROR")
            return False
        
        # Rebuild and restart containers
        log("Rebuilding containers...")
        result = subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            cwd=f"{REPO_PATH}/docker",
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stdout.strip():
            log(f"Docker: {result.stdout.strip()}")
        if result.returncode != 0:
            log(f"Docker compose failed: {result.stderr}", "ERROR")
            return False
        
        log("Deployment complete!", "SUCCESS")
        return True
        
    except subprocess.TimeoutExpired:
        log("Deployment timed out", "ERROR")
        return False
    except Exception as e:
        log(f"Deployment failed: {e}", "ERROR")
        return False


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    """Handle GitHub webhook requests."""
    
    # Silence default logging - we handle it ourselves
    def log_message(self, format, *args):
        pass
    
    def log_request(self, code='-', size='-'):
        # Only log non-trivial requests
        pass
    
    def _send_json(self, status: int, data: dict):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_POST(self):
        client_ip = self.client_address[0]
        
        if self.path != "/deploy":
            # Don't log 404s for random probes
            self.send_response(404)
            self.end_headers()
            return
        
        # Check for GitHub headers first (quick reject non-GitHub requests)
        user_agent = self.headers.get("User-Agent", "")
        if not user_agent.startswith("GitHub-Hookshot/"):
            log(f"Rejected non-GitHub request from {client_ip}", "WARN")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return
        
        # Read payload
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 1_000_000:  # 1MB limit
                log(f"Payload too large from {client_ip}: {content_length}", "WARN")
                self.send_response(413)
                self.end_headers()
                return
            payload = self.rfile.read(content_length)
        except Exception as e:
            log(f"Failed to read payload from {client_ip}: {e}", "ERROR")
            self.send_response(400)
            self.end_headers()
            return
        
        # Verify signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(payload, signature):
            log(f"Invalid signature from {client_ip}", "WARN")
            self._send_json(403, {"error": "Invalid signature"})
            return
        
        # Parse event
        event = self.headers.get("X-GitHub-Event", "")
        delivery_id = self.headers.get("X-GitHub-Delivery", "unknown")
        
        if event == "ping":
            log(f"Received ping from GitHub (delivery: {delivery_id})")
            self._send_json(200, {"message": "pong", "delivery": delivery_id})
            return
        
        if event != "push":
            log(f"Ignored event '{event}' (delivery: {delivery_id})")
            self._send_json(200, {"message": f"Ignored event: {event}"})
            return
        
        # Check branch
        try:
            data = json.loads(payload)
            ref = data.get("ref", "")
            pusher = data.get("pusher", {}).get("name", "unknown")
            
            if ref != f"refs/heads/{BRANCH}":
                log(f"Ignored push to {ref} by {pusher}")
                self._send_json(200, {"message": f"Ignored branch: {ref}"})
                return
            
            log(f"Received push to {BRANCH} by {pusher} (delivery: {delivery_id})")
            
        except json.JSONDecodeError as e:
            log(f"Invalid JSON payload: {e}", "ERROR")
            self._send_json(400, {"error": "Invalid JSON"})
            return
        
        # Respond immediately, deploy in background
        self._send_json(200, {"message": "Deployment started", "delivery": delivery_id})
        
        # Run deployment in background thread
        thread = threading.Thread(target=deploy, daemon=True)
        thread.start()
    
    def do_GET(self):
        """Health check endpoint."""
        if self.path == "/health":
            self._send_json(200, {
                "status": "healthy",
                "repo": REPO_PATH,
                "branch": BRANCH,
                "secret_configured": bool(WEBHOOK_SECRET),
            })
        elif self.path == "/":
            # Simple response for root path (scanners often hit this)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"TCG Webhook Server")
        else:
            self.send_response(404)
            self.end_headers()


class RobustTCPServer(socketserver.TCPServer):
    """TCP server that handles connection errors gracefully."""
    
    allow_reuse_address = True
    
    def handle_error(self, request, client_address):
        """Handle errors without crashing - suppress scanner noise."""
        import sys
        exc_type, exc_value, _ = sys.exc_info()
        
        # Ignore connection reset errors (from scanners/bots)
        if exc_type in (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            # Silently ignore - these are just scanners
            return
        
        # Log other errors
        log(f"Error handling request from {client_address}: {exc_type.__name__}: {exc_value}", "ERROR")


def main():
    banner = f"""
╔═══════════════════════════════════════════════════════════╗
║           TCG Auto-Deploy Webhook Server                  ║
╠═══════════════════════════════════════════════════════════╣
║  Port: {PORT:<51} ║
║  Repo: {REPO_PATH:<51} ║
║  Branch: {BRANCH:<49} ║
║  Secret: {'✓ Configured' if WEBHOOK_SECRET else '✗ NOT SET':<49} ║
╚═══════════════════════════════════════════════════════════╝
"""
    print(banner)
    
    if not WEBHOOK_SECRET:
        log("WEBHOOK_SECRET not set - webhook signature verification disabled!", "WARN")
        log("Set it with: export WEBHOOK_SECRET=your-secret-here", "WARN")
        print()
    
    log(f"Starting server on 0.0.0.0:{PORT}")
    
    server = RobustTCPServer(("0.0.0.0", PORT), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
