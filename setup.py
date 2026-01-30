#!/usr/bin/env python3
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.

"""
FuzzForge Setup Script - One-command setup for development

This script automates the entire FuzzForge development setup process,
from checking prerequisites to running your first security scan.
"""

import os
import sys
import subprocess
import platform
import time
from pathlib import Path
from typing import List, Tuple


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


class FuzzForgeSetup:
    """Automated FuzzForge development environment setup"""

    def __init__(self):
        self.system = platform.system().lower()
        self.project_root = Path(__file__).parent
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def print_header(self):
        """Print welcome header"""
        print(f"""{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════╗
║           FuzzForge Setup Script           ║
║       Automated Development Setup        ║
╚══════════════════════════════════════════╝
{Colors.END}""")
        print(f"{Colors.WHITE}Welcome to FuzzForge! This script will set up your development environment.{Colors.END}\n")

    def run_command(self, command: str, description: str, critical: bool = True) -> Tuple[bool, str]:
        """Run a shell command and return success status and output"""
        print(f"{Colors.YELLOW}🔄 {description}...{Colors.END}")

        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ {description} completed successfully{Colors.END}")
                return True, result.stdout
            else:
                error_msg = f"{description} failed: {result.stderr.strip()}"
                if critical:
                    self.errors.append(error_msg)
                    print(f"{Colors.RED}❌ {error_msg}{Colors.END}")
                else:
                    self.warnings.append(error_msg)
                    print(f"{Colors.YELLOW}⚠️  {error_msg}{Colors.END}")
                return False, result.stderr

        except subprocess.TimeoutExpired:
            error_msg = f"{description} timed out"
            if critical:
                self.errors.append(error_msg)
            else:
                self.warnings.append(error_msg)
            print(f"{Colors.RED}⏰ {error_msg}{Colors.END}")
            return False, "Timeout"

        except Exception as e:
            error_msg = f"{description} failed with exception: {e}"
            if critical:
                self.errors.append(error_msg)
            else:
                self.warnings.append(error_msg)
            print(f"{Colors.RED}💥 {error_msg}{Colors.END}")
            return False, str(e)

    def check_prerequisites(self) -> bool:
        """Check if required tools are installed"""
        print(f"{Colors.BOLD}📋 Step 1: Checking Prerequisites{Colors.END}\n")

        all_good = True

        # Check Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        if sys.version_info >= (3, 11):
            print(f"{Colors.GREEN}✅ Python {python_version} (required: 3.11+){Colors.END}")
        else:
            print(f"{Colors.RED}❌ Python {python_version} (required: 3.11+){Colors.END}")
            self.errors.append(f"Python version {python_version} is too old. Please install Python 3.11+")
            all_good = False

        # Check Docker daemon is running
        docker_success, docker_output = self.run_command("docker ps", "Checking Docker", critical=False)
        if not docker_success:
            self.errors.append("Docker daemon is not running. Please start Docker Desktop")
            all_good = False

        # Check Docker Compose with actual compose file validation
        if docker_success:
            compose_success, _ = self.run_command("docker compose config --quiet", "Checking Docker Compose", critical=False)
            if not compose_success:
                self.errors.append("Docker Compose validation failed. Please ensure docker-compose.yaml is valid and Docker is running")
                all_good = False
        else:
            print(f"{Colors.RED}❌ Checking Docker Compose failed: Docker daemon not running{Colors.END}")
            self.errors.append("Docker Compose cannot be validated - Docker daemon not running")
            all_good = False

        # Check UV
        uv_success, _ = self.run_command("uv --version", "Checking UV package manager", critical=False)
        if not uv_success:
            print(f"{Colors.YELLOW}📦 UV not found, installing UV...{Colors.END}")
            if self.system == "darwin":  # macOS
                subprocess.run(["curl", "-LsSf", "https://astral.sh/uv/install.sh", "|", "sh"], shell=True)
            else:
                subprocess.run(["pip", "install", "uv"])

            # Recheck UV
            uv_success, _ = self.run_command("uv --version", "Re-checking UV installation", critical=False)
            if not uv_success:
                self.warnings.append("UV installation failed. You can install it manually later")

        return all_good

    def setup_docker_environment(self) -> bool:
        """Set up Docker environment"""
        print(f"\n{Colors.BOLD}🐳 Step 2: Setting Up Docker Environment{Colors.END}\n")

        # Check if Docker daemon is running
        docker_running, _ = self.run_command("docker ps", "Checking Docker daemon", critical=False)
        if not docker_running:
            print(f"{Colors.YELLOW}⚠️  Docker daemon is not running. Please start Docker Desktop and try again.{Colors.END}")
            return False

        # Start FuzzForge services
        os.chdir(self.project_root)

        # Warning about first launch
        print(f"{Colors.CYAN}ℹ️  First launch will take longer due to Docker image building (5-10 minutes).{Colors.END}")
        print(f"{Colors.CYAN}   Subsequent starts will be much faster!{Colors.END}\n")

        # Build and start services
        print(f"{Colors.YELLOW}🔨 Building and starting FuzzForge services (this may take a while)...{Colors.END}")

        # Use longer timeout for Docker build (10 minutes)
        try:
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for Docker build
                cwd=self.project_root
            )

            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ Docker services started successfully{Colors.END}")
            else:
                self.errors.append(f"Docker services failed to start: {result.stderr.strip()}")
                print(f"{Colors.RED}❌ Docker services failed to start: {result.stderr.strip()}{Colors.END}")
                return False

        except subprocess.TimeoutExpired:
            self.errors.append("Docker build timed out after 10 minutes")
            print(f"{Colors.RED}⏰ Docker build timed out after 10 minutes{Colors.END}")
            return False
        except Exception as e:
            self.errors.append(f"Docker setup failed: {e}")
            print(f"{Colors.RED}💥 Docker setup failed: {e}{Colors.END}")
            return False

        # Wait for services to be ready with extended timeout
        print(f"{Colors.YELLOW}⏳ Waiting for services to be ready...{Colors.END}")
        for i in range(120):  # Wait up to 2 minutes for services to be ready
            time.sleep(1)
            health_success, _ = self.run_command("curl -s http://localhost:8000/health", "Health check", critical=False)
            if health_success:
                print(f"\n{Colors.GREEN}✅ FuzzForge API is ready at http://localhost:8000!{Colors.END}")
                return True
            if i % 10 == 0:  # Print progress every 10 seconds
                print(f"\n{Colors.CYAN}   Still starting... ({i+1}s){Colors.END}")
            else:
                print(".", end="", flush=True)

        print(f"\n{Colors.YELLOW}⚠️  Services may still be starting. Check status with 'docker compose logs'{Colors.END}")
        print(f"{Colors.CYAN}💡 You can monitor progress with: docker compose logs -f{Colors.END}")
        return True

    def install_cli(self) -> bool:
        """Install FuzzForge CLI"""
        print(f"\n{Colors.BOLD}💻 Step 3: Installing FuzzForge CLI (Final Step){Colors.END}\n")

        cli_dir = self.project_root / "cli"
        if not cli_dir.exists():
            self.errors.append("CLI directory not found")
            return False

        # Install from root, pointing to the 'cli' directory
        success, _ = self.run_command("uv tool install --python python3.12 .", "Installing FuzzForge CLI with Python 3.12")

        return success

    def print_next_steps(self):
        """Print next steps for the user"""
        print(f"\n{Colors.BOLD}{Colors.GREEN}🎉 Setup Complete!{Colors.END}")

        if not self.errors:
            print(f"""
{Colors.CYAN}🚀 FuzzForge is now ready! Here's what you can do next:{Colors.END}

{Colors.BOLD}📖 Learn More:{Colors.END}
  • {Colors.BLUE}docs/QUICKSTART.md{Colors.END} - 5-minute module creation tutorial
  • {Colors.BLUE}docs/PATTERNS.md{Colors.END} - Common patterns and recipes
  • {Colors.BLUE}cli/README.md{Colors.END} - Complete CLI documentation

{Colors.BOLD}🔍 Try Some Commands:{Colors.END}
  • {Colors.WHITE}cd test_projects/vulnerable_app{Colors.END} - Navigate to test project
  • {Colors.WHITE}fuzzforge init{Colors.END} - Initialize a FuzzForge project
  • {Colors.WHITE}ff workflow security_assessment .{Colors.END} - Run security assessment
  • {Colors.WHITE}ff workflow secret_detection_scan .{Colors.END} - Run secret detection
  • {Colors.WHITE}fuzzforge status{Colors.END} - Check project and workflow status
  • {Colors.WHITE}fuzzforge --help{Colors.END} - See all available commands

{Colors.BOLD}🔧 Available Workflows:{Colors.END}
  • {Colors.CYAN}security_assessment{Colors.END} - Comprehensive security scanning
  • {Colors.CYAN}secret_detection_scan{Colors.END} - Credential and secret detection

{Colors.BOLD}🌐 Web Interface:{Colors.END}
  • API: {Colors.WHITE}http://localhost:8000{Colors.END}
  • Health: {Colors.WHITE}http://localhost:8000/health{Colors.END}
  • API Docs: {Colors.WHITE}http://localhost:8000/docs{Colors.END}
""")

        if self.warnings:
            print(f"\n{Colors.YELLOW}⚠️  Warnings:{Colors.END}")
            for warning in self.warnings:
                print(f"  • {warning}")

        if self.errors:
            print(f"\n{Colors.RED}❌ Errors that need attention:{Colors.END}")
            for error in self.errors:
                print(f"  • {error}")
            print(f"\n{Colors.YELLOW}🔧 Please fix these issues and run the setup again.{Colors.END}")

    def run(self):
        """Run the complete setup process"""
        self.print_header()

        # Step 1: Prerequisites
        if not self.check_prerequisites():
            if self.errors:
                self.print_next_steps()
                return False

        # Step 2: Docker setup
        if not self.setup_docker_environment():
            if self.errors:
                self.print_next_steps()
                return False

        # Step 3: CLI installation
        self.install_cli()

        # Final summary
        self.print_next_steps()

        return len(self.errors) == 0


def main():
    """Main entry point"""
    setup = FuzzForgeSetup()

    try:
        success = setup.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Setup interrupted by user. You can run this script again anytime.{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.END}")
        print(f"{Colors.YELLOW}Please report this issue with the error details above.{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()
