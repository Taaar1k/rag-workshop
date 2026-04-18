"""
Service Orchestrator for RAG Core System

This module provides unified start/stop commands for all RAG services
with health checks, dependency validation, and cross-platform support.
"""

import os
import sys
import signal
import subprocess
import time
import platform
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import yaml


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('service_orchestrator')


class ServiceState(Enum):
    """Current state of a service"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class ServiceConfig:
    """Configuration for a service"""
    name: str
    command: List[str]
    health_check_url: Optional[str] = None
    health_check_interval: float = 1.0
    startup_timeout: float = 30.0
    shutdown_timeout: float = 5.0
    dependencies: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class ServiceStatus:
    """Current status of a service"""
    name: str
    state: ServiceState = ServiceState.STOPPED
    pid: Optional[int] = None
    process: Optional[subprocess.Popen] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None


class ServiceManager:
    """Manages RAG system services with health checks and dependency validation"""
    
    def __init__(self, config_dir: str = None):
        self.config_dir = config_dir or "./config"
        self.services: Dict[str, ServiceStatus] = {}
        self.service_configs = self._load_service_configs()
        self.platform = platform.system().lower()
    
    def _load_service_configs(self) -> Dict[str, ServiceConfig]:
        """Load service configurations from config files"""
        config_path = Path(self.config_dir) / "services.yaml"
        
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return self._get_default_configs()
        
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            return self._parse_service_configs(config_data)
        except Exception as e:
            logger.error(f"Failed to load service config: {e}")
            return self._get_default_configs()
    
    def _get_default_configs(self) -> Dict[str, ServiceConfig]:
        """Return default service configurations"""
        return {
            "mcp_server": ServiceConfig(
                name="mcp_server",
                command=["python", "src/mcp_server.py"],
                health_check_url="http://localhost:8000/health",
                startup_timeout=15.0,
                shutdown_timeout=5.0
            ),
            "embedding_model": ServiceConfig(
                name="embedding_model",
                command=["python", "-c", "from sentence_transformers import SentenceTransformer; print('ready')"],
                health_check_url=None,
                startup_timeout=60.0,
                shutdown_timeout=2.0
            ),
            "llm": ServiceConfig(
                name="llm",
                command=[
                    "llama.cpp",
                    "-m", os.getenv("LLM_MODEL_PATH", "models/llm/default.gguf"),
                    "-c", "2048"
                ],
                health_check_url="http://localhost:8080/health",
                startup_timeout=30.0,
                shutdown_timeout=5.0
            )
        }
    
    def _parse_service_configs(self, config_data: Dict) -> Dict[str, ServiceConfig]:
        """Parse service configurations from YAML data"""
        services = {}
        services_config = config_data.get('services', {})
        
        for name, config in services_config.items():
            if not config.get('enabled', True):
                continue
            
            health_check = config.get('health_check', {})
            services[name] = ServiceConfig(
                name=name,
                command=config.get('command', []),
                health_check_url=health_check.get('endpoint'),
                health_check_interval=health_check.get('interval', 1.0),
                startup_timeout=config.get('startup_timeout', 30.0),
                shutdown_timeout=config.get('shutdown_timeout', 5.0),
                dependencies=config.get('dependencies', []),
                enabled=config.get('enabled', True)
            )
        
        return services
    
    def start_service(self, service_name: str) -> Tuple[bool, str]:
        """Start a single service with health check
        
        Returns:
            Tuple of (success, error_message)
        """
        config = self.service_configs.get(service_name)
        if not config:
            logger.error(f"Service {service_name} not found")
            return False, f"Service {service_name} not found"
        
        if not config.enabled:
            logger.warning(f"Service {service_name} is disabled")
            return True, f"Service {service_name} is disabled, skipping"
        
        logger.info(f"Starting service: {service_name}")
        
        # Check dependencies first
        if not self._validate_dependencies([service_name]):
            error_msg = f"Dependency validation failed for {service_name}"
            logger.error(error_msg)
            return False, error_msg
        
        try:
            # Start process
            process = subprocess.Popen(
                config.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True if self.platform != 'windows' else False
            )
            
            self.services[service_name] = ServiceStatus(
                name=service_name,
                state=ServiceState.STARTING,
                pid=process.pid,
                process=process,
                start_time=time.time()
            )
            
            # Wait for health check if URL provided
            if config.health_check_url:
                if not self._wait_for_health_check(config.health_check_url, config.startup_timeout):
                    error_msg = f"Service {service_name} failed health check"
                    logger.error(error_msg)
                    self.stop_service(service_name)
                    return False, error_msg
            
            self.services[service_name].state = ServiceState.RUNNING
            logger.info(f"Service {service_name} started successfully (PID: {process.pid})")
            return True, ""
            
        except Exception as e:
            error_msg = f"Failed to start service {service_name}: {e}"
            logger.error(error_msg)
            if service_name in self.services:
                del self.services[service_name]
            return False, error_msg
    
    def _wait_for_health_check(self, url: str, timeout: float) -> bool:
        """Wait for service health check to pass"""
        import requests
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=1)
                if response.status_code == 200:
                    return True
            except:
                pass
            time.sleep(0.5)
        return False
    
    def start_all_services(self) -> Tuple[bool, List[str]]:
        """Start all RAG services in correct order
        
        Returns:
            Tuple of (success, error_messages)
        """
        logger.info("Starting all RAG services...")
        
        # Validate all dependencies first
        if not self._validate_dependencies():
            error_msg = "Dependency validation failed"
            logger.error(error_msg)
            return False, [error_msg]
        
        # Get start order from config or use default
        global_config = self.service_configs.get('global', {})
        start_order = global_config.get('start_order', ['llm', 'embedding_model', 'mcp_server'])
        
        success = True
        errors = []
        
        for service_name in start_order:
            if service_name not in self.service_configs:
                continue
                
            if not self.service_configs[service_name].enabled:
                logger.info(f"Skipping disabled service: {service_name}")
                continue
            
            result, error = self.start_service(service_name)
            if not result:
                logger.error(f"Failed to start {service_name}: {error}")
                success = False
                errors.append(error)
                # Don't stop other services - let user decide
                break
        
        if success:
            logger.info("All services started successfully")
        
        return success, errors
    
    def stop_service(self, service_name: str, timeout: float = None) -> Tuple[bool, str]:
        """Stop a single service gracefully
        
        Returns:
            Tuple of (success, error_message)
        """
        status = self.services.get(service_name)
        if not status or status.state == ServiceState.STOPPED:
            logger.warning(f"Service {service_name} not running")
            return True, f"Service {service_name} not running"
        
        if timeout is None:
            config = self.service_configs.get(service_name)
            timeout = config.shutdown_timeout if config else 5.0
        
        logger.info(f"Stopping service: {service_name} (PID: {status.pid})")
        
        try:
            process = status.process
            
            # Send SIGTERM
            if self.platform == 'windows':
                process.terminate()
            else:
                process.send_signal(signal.SIGTERM)
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Force kill if still running
                logger.warning(f"Service {service_name} did not stop gracefully, killing...")
                process.kill()
                process.wait()
            
            status.state = ServiceState.STOPPED
            status.end_time = time.time()
            del self.services[service_name]
            logger.info(f"Service {service_name} stopped successfully")
            return True, ""
            
        except Exception as e:
            error_msg = f"Error stopping service {service_name}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def stop_all_services(self, timeout: float = None) -> Tuple[bool, List[str]]:
        """Stop all services gracefully
        
        Returns:
            Tuple of (success, error_messages)
        """
        logger.info("Stopping all RAG services...")
        
        if timeout is None:
            global_config = self.service_configs.get('global', {})
            timeout = global_config.get('graceful_shutdown_timeout', 5.0)
        
        # Stop services in reverse order
        start_order = ['llm', 'embedding_model', 'mcp_server']
        stop_order = list(reversed(start_order))
        
        success = True
        errors = []
        
        for service_name in stop_order:
            if service_name not in self.services:
                continue
            
            result, error = self.stop_service(service_name, timeout)
            if not result:
                logger.error(f"Failed to stop {service_name}: {error}")
                success = False
                errors.append(error)
        
        if success:
            logger.info("All services stopped successfully")
        
        return success, errors
    
    def _validate_dependencies(self, services: List[str] = None) -> bool:
        """Validate all dependencies before startup
        
        Args:
            services: List of services to validate. If None, validate all enabled services.
            
        Returns:
            True if all dependencies are met, False otherwise
        """
        logger.info("Validating dependencies...")
        
        # Get services to validate
        if services is None:
            services = [name for name, config in self.service_configs.items() if config.enabled]
        
        # Check required files
        dependencies_config = self.service_configs.get('dependencies', {})
        required_files = dependencies_config.get('required_files', [])
        
        for file_path in required_files:
            if not Path(file_path).exists():
                logger.error(f"Required file not found: {file_path}")
                return False
        
        # Check required packages
        required_packages = dependencies_config.get('required_packages', [])
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                logger.error(f"Missing dependency: {package}")
                return False
        
        logger.info("All dependencies validated")
        return True
    
    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        """Get current status of a service"""
        return self.services.get(service_name)
    
    def get_all_statuses(self) -> Dict[str, ServiceStatus]:
        """Get status of all managed services"""
        return self.services.copy()
    
    def is_service_running(self, service_name: str) -> bool:
        """Check if a service is currently running"""
        status = self.services.get(service_name)
        if not status:
            return False
        return status.state == ServiceState.RUNNING
    
    def restart_service(self, service_name: str) -> Tuple[bool, str]:
        """Restart a service (stop then start)"""
        logger.info(f"Restarting service: {service_name}")
        
        # Stop the service
        success, error = self.stop_service(service_name)
        if not success:
            return False, f"Failed to stop service: {error}"
        
        # Start the service
        return self.start_service(service_name)


class CoreController:
    """Main controller for RAG system lifecycle"""
    
    def __init__(self, config_dir: str = None):
        self.service_manager = ServiceManager(config_dir)
    
    def start(self) -> Tuple[bool, List[str]]:
        """Start the entire RAG system"""
        return self.service_manager.start_all_services()
    
    def stop(self, timeout: float = None) -> Tuple[bool, List[str]]:
        """Stop the entire RAG system"""
        return self.service_manager.stop_all_services(timeout)
    
    def restart(self, timeout: float = None) -> Tuple[bool, List[str]]:
        """Restart the entire RAG system"""
        success, errors = self.stop(timeout)
        if not success:
            return False, errors
        return self.start()
    
    def status(self) -> Dict[str, ServiceStatus]:
        """Get status of all services"""
        return self.service_manager.get_all_statuses()


def main():
    """Command-line interface for core_start/core_stop commands"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="RAG Core Service Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python service_orchestrator.py start
  python service_orchestrator.py stop --timeout 10
  python service_orchestrator.py restart
  python service_orchestrator.py status
        """
    )
    
    parser.add_argument(
        'command',
        choices=['start', 'stop', 'restart', 'status'],
        help='Command to execute'
    )
    parser.add_argument(
        '--config', '-c',
        help='Config file path'
    )
    parser.add_argument(
        '--timeout', '-t',
        type=float,
        default=5.0,
        help='Shutdown timeout in seconds'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    controller = CoreController(config_dir=args.config)
    
    if args.command == 'start':
        success, errors = controller.start()
        if success:
            print("RAG Core services started successfully")
            print("Press Ctrl+C to stop")
            try:
                # Keep running
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping services...")
                controller.stop()
        else:
            print("Failed to start RAG Core services:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
    
    elif args.command == 'stop':
        success, errors = controller.stop(timeout=args.timeout)
        if success:
            print("RAG Core services stopped successfully")
        else:
            print("Failed to stop RAG Core services:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
    
    elif args.command == 'restart':
        success, errors = controller.restart(timeout=args.timeout)
        if success:
            print("RAG Core services restarted successfully")
        else:
            print("Failed to restart RAG Core services:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
    
    elif args.command == 'status':
        statuses = controller.status()
        print("RAG Core Service Status:")
        for name, status in statuses.items():
            print(f"  {name}: {status.state.value} (PID: {status.pid})")


if __name__ == "__main__":
    main()
