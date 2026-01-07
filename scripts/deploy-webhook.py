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
import subprocess
import threading

# Configuration
PORT = 9000
REPO_PATH = "/var/lib/Odoo_TCG"  # Where the repo is cloned
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
BRANCH = "main"


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature."""
    if not WEBHOOK_SECRET:
        print("⚠️  No WEBHOOK_SECRET set - skipping signature verification")
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
    print("🚀 Starting deployment...")
    
    try:
        # Pull latest code
        print("📥 Pulling latest code...")
        result = subprocess.run(
            ["git", "pull", "origin", BRANCH],
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            timeout=60,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"❌ Git pull failed: {result.stderr}")
            return False
        
        # Rebuild and restart containers
        print("🔨 Rebuilding containers...")
        result = subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            cwd=f"{REPO_PATH}/docker",
            capture_output=True,
            text=True,
            timeout=300,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"❌ Docker compose failed: {result.stderr}")
            return False
        
        print("✅ Deployment complete!")
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Deployment timed out")
        return False
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        return False


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    """Handle GitHub webhook requests."""
    
    def do_POST(self):
        if self.path != "/deploy":
            self.send_response(404)
            self.end_headers()
            return
        
        # Read payload
        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)
        
        # Verify signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(payload, signature):
            print("❌ Invalid signature")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return
        
        # Parse event
        event = self.headers.get("X-GitHub-Event", "")
        if event != "push":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"Ignored event: {event}".encode())
            return
        
        # Check branch
        try:
            data = json.loads(payload)
            ref = data.get("ref", "")
            if ref != f"refs/heads/{BRANCH}":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(f"Ignored branch: {ref}".encode())
                return
        except json.JSONDecodeError:
            pass
        
        # Respond immediately, deploy in background
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Deployment started")
        
        # Run deployment in background thread
        thread = threading.Thread(target=deploy)
        thread.start()
    
    def do_GET(self):
        """Health check endpoint."""
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[Webhook] {args[0]}")


def main():
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║           TCG Auto-Deploy Webhook Server                  ║
╠═══════════════════════════════════════════════════════════╣
║  Listening on port: {PORT}                                   ║
║  Repo path: {REPO_PATH:<43} ║
║  Branch: {BRANCH:<47} ║
║  Webhook URL: http://YOUR-IP:{PORT}/deploy                  ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    if not WEBHOOK_SECRET:
        print("⚠️  WARNING: WEBHOOK_SECRET not set!")
        print("   Set it with: export WEBHOOK_SECRET=your-secret-here")
        print()
    
    server = http.server.HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()

