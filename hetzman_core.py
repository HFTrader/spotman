#!/usr/bin/env python3
"""
Hetzman Core - Hetzner Robot API Client

Core functionality for managing Hetzner dedicated servers via the Robot API.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
from requests.auth import HTTPBasicAuth


# Robot API base URL
ROBOT_API_BASE = "https://robot-ws.your-server.de"


class HetznerError(Exception):
    """Base exception for Hetzner API errors."""
    pass


class HetznerAuthError(HetznerError):
    """Authentication error."""
    pass


class HetznerNotFoundError(HetznerError):
    """Resource not found."""
    pass


class HetznerManager:
    """Manage Hetzner dedicated servers via Robot API."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        quiet: bool = False
    ):
        """
        Initialize Hetzner manager.

        Args:
            username: Robot API username (or HETZNER_USER env var)
            password: Robot API password (or HETZNER_PASS env var)
            quiet: Suppress output messages
        """
        self.username = username or os.environ.get("HETZNER_USER")
        self.password = password or os.environ.get("HETZNER_PASS")
        self.quiet = quiet

        if not self.username or not self.password:
            raise HetznerAuthError(
                "Hetzner credentials required. Set HETZNER_USER and HETZNER_PASS "
                "environment variables or pass username/password."
            )

        self.auth = HTTPBasicAuth(self.username, self.password)

    def _log(self, msg: str):
        """Print message if not quiet."""
        if not self.quiet:
            print(msg)

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        expected_status: list[int] | None = None
    ) -> dict | list:
        """
        Make authenticated request to Robot API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint (e.g., /server)
            data: POST data
            expected_status: List of expected status codes

        Returns:
            JSON response

        Raises:
            HetznerError: On API error
        """
        url = f"{ROBOT_API_BASE}{endpoint}"
        expected = expected_status or [200]

        try:
            response = requests.request(
                method,
                url,
                auth=self.auth,
                data=data,
                timeout=30
            )
        except requests.RequestException as e:
            raise HetznerError(f"Request failed: {e}")

        if response.status_code == 401:
            raise HetznerAuthError("Invalid credentials")

        if response.status_code == 404:
            raise HetznerNotFoundError(f"Not found: {endpoint}")

        if response.status_code not in expected:
            raise HetznerError(
                f"API error {response.status_code}: {response.text}"
            )

        if response.text:
            return response.json()
        return {}

    # =========================================================================
    # SERVER LISTING
    # =========================================================================

    def list_servers(self) -> List[Dict[str, Any]]:
        """
        List all servers.

        Returns:
            List of server info dicts
        """
        result = self._request("GET", "/server")
        servers = []

        for item in result:
            server = item.get("server", item)
            servers.append({
                "ip": server.get("server_ip"),
                "name": server.get("server_name"),
                "product": server.get("product"),
                "datacenter": server.get("dc"),
                "status": server.get("status"),
                "cancelled": server.get("cancelled", False),
            })

        return servers

    def get_server(self, server_ip: str) -> Dict[str, Any]:
        """
        Get server details.

        Args:
            server_ip: Server IP address

        Returns:
            Server info dict
        """
        result = self._request("GET", f"/server/{server_ip}")
        server = result.get("server", result)

        return {
            "ip": server.get("server_ip"),
            "name": server.get("server_name"),
            "product": server.get("product"),
            "datacenter": server.get("dc"),
            "status": server.get("status"),
            "cancelled": server.get("cancelled", False),
            "paid_until": server.get("paid_until"),
        }

    # =========================================================================
    # RESET / RESCUE
    # =========================================================================

    def reset_server(self, server_ip: str, reset_type: str = "hw") -> Dict[str, Any]:
        """
        Reset a server.

        Args:
            server_ip: Server IP address
            reset_type: Reset type (sw=software, hw=hardware, man=manual)

        Returns:
            Reset result
        """
        self._log(f"Resetting server {server_ip} ({reset_type})...")

        result = self._request(
            "POST",
            f"/reset/{server_ip}",
            data={"type": reset_type}
        )

        return result.get("reset", result)

    def get_rescue_status(self, server_ip: str) -> Dict[str, Any]:
        """
        Get rescue system status.

        Args:
            server_ip: Server IP address

        Returns:
            Rescue status
        """
        result = self._request("GET", f"/boot/{server_ip}/rescue")
        return result.get("rescue", result)

    def activate_rescue(
        self,
        server_ip: str,
        os: str = "linux",
        arch: int = 64,
        authorized_key: str | None = None
    ) -> Dict[str, Any]:
        """
        Activate rescue system.

        Args:
            server_ip: Server IP address
            os: Operating system (linux, linuxold, vkvm)
            arch: Architecture (32 or 64)
            authorized_key: SSH key fingerprint

        Returns:
            Rescue activation result with password
        """
        self._log(f"Activating rescue mode on {server_ip}...")

        data = {"os": os, "arch": arch}
        if authorized_key:
            data["authorized_key"] = authorized_key

        result = self._request(
            "POST",
            f"/boot/{server_ip}/rescue",
            data=data
        )

        rescue = result.get("rescue", result)

        if rescue.get("password"):
            self._log(f"Rescue password: {rescue['password']}")

        return rescue

    def deactivate_rescue(self, server_ip: str) -> Dict[str, Any]:
        """
        Deactivate rescue system.

        Args:
            server_ip: Server IP address

        Returns:
            Result
        """
        self._log(f"Deactivating rescue mode on {server_ip}...")

        result = self._request("DELETE", f"/boot/{server_ip}/rescue")
        return result.get("rescue", result)

    # =========================================================================
    # SSH KEY MANAGEMENT
    # =========================================================================

    def list_ssh_keys(self) -> List[Dict[str, Any]]:
        """
        List registered SSH keys.

        Returns:
            List of SSH key info
        """
        result = self._request("GET", "/key")
        keys = []

        for item in result:
            key = item.get("key", item)
            keys.append({
                "name": key.get("name"),
                "fingerprint": key.get("fingerprint"),
                "type": key.get("type"),
                "size": key.get("size"),
            })

        return keys

    # =========================================================================
    # CANCELLATION
    # =========================================================================

    def cancel_server(
        self,
        server_ip: str,
        cancellation_date: str | None = None
    ) -> Dict[str, Any]:
        """
        Cancel a server.

        Args:
            server_ip: Server IP address
            cancellation_date: Date in YYYY-MM-DD format (None = earliest)

        Returns:
            Cancellation result
        """
        self._log(f"Cancelling server {server_ip}...")

        data = {}
        if cancellation_date:
            data["cancellation_date"] = cancellation_date

        result = self._request(
            "POST",
            f"/server/{server_ip}/cancellation",
            data=data if data else None
        )

        return result.get("cancellation", result)

    def revoke_cancellation(self, server_ip: str) -> Dict[str, Any]:
        """
        Revoke server cancellation.

        Args:
            server_ip: Server IP address

        Returns:
            Result
        """
        self._log(f"Revoking cancellation for {server_ip}...")

        result = self._request("DELETE", f"/server/{server_ip}/cancellation")
        return result

    # =========================================================================
    # PROVISIONING (via SSH)
    # =========================================================================

    def wait_for_ssh(
        self,
        server_ip: str,
        timeout: int = 300,
        interval: int = 10
    ) -> bool:
        """
        Wait for SSH to become available.

        Args:
            server_ip: Server IP address
            timeout: Max wait time in seconds
            interval: Check interval in seconds

        Returns:
            True if SSH is available
        """
        self._log(f"Waiting for SSH on {server_ip}...")

        start = time.time()
        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                     f"root@{server_ip}", "echo ok"],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self._log(f"SSH available on {server_ip}")
                    return True
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass

            time.sleep(interval)

        return False

    def run_ssh_command(
        self,
        server_ip: str,
        command: str,
        timeout: int = 60
    ) -> tuple[int, str, str]:
        """
        Run command via SSH.

        Args:
            server_ip: Server IP address
            command: Command to run
            timeout: Command timeout

        Returns:
            (returncode, stdout, stderr)
        """
        try:
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{server_ip}", command],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    def provision_preempt_rt(
        self,
        server_ip: str,
        ssh_pubkey: str | None = None,
        housekeeping_cpus: int = 2
    ) -> bool:
        """
        Provision server with PREEMPT-RT setup.

        Assumes server is in rescue mode.

        Args:
            server_ip: Server IP address
            ssh_pubkey: Path to SSH public key
            housekeeping_cpus: Number of CPUs for housekeeping

        Returns:
            True if successful
        """
        # Find setup script
        script_paths = [
            Path(__file__).parent / "scripts" / "setup-preempt-rt.sh",
            Path.home() / "git" / "tests" / "substack" / "hft" /
            "preempt-rt-benchmarks" / "setup-preempt-rt.sh",
        ]

        setup_script = None
        for path in script_paths:
            if path.exists():
                setup_script = path
                break

        if not setup_script:
            self._log("ERROR: setup-preempt-rt.sh not found")
            return False

        self._log(f"Running PREEMPT-RT setup on {server_ip}...")

        cmd = [str(setup_script), f"root@{server_ip}"]
        if ssh_pubkey:
            cmd.append(ssh_pubkey)

        try:
            result = subprocess.run(
                cmd,
                timeout=1800,  # 30 minutes
                check=False
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self._log("Setup timed out")
            return False
        except Exception as e:
            self._log(f"Setup failed: {e}")
            return False
