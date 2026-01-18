# Changelog

All notable changes to Debai will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

### Changed
- Nothing yet

### Fixed
- Nothing yet

## [1.0.0] - 2026-01-18

### Added
- Initial release of Debai
- AI agent management with support for multiple agent types
  - System maintenance agents
  - Package management agents
  - Configuration management agents
  - Resource monitoring agents
  - Security monitoring agents
  - Backup management agents
  - Network configuration agents
  - Custom user-defined agents
- Integration with Docker Model Runner for local AI models
- Integration with cagent for agent execution
- Command-line interface (CLI) with rich terminal output
  - `debai status` - Show system status
  - `debai init` - Initialize environment
  - `debai agent` - Agent management commands
  - `debai model` - Model management commands
  - `debai task` - Task management commands
  - `debai generate` - Image generation commands
  - `debai monitor` - Real-time resource monitoring
- GTK4/Adwaita graphical user interface
  - Dashboard with system metrics
  - Agent management panel
  - Model browser and downloader
  - Task scheduler
  - Image generator
  - Preferences dialog
- Image generation capabilities
  - ISO image generation for bootable distributions
  - QCOW2 image generation for QEMU/KVM
  - Docker Compose configuration generation
- Pre-configured agent templates
  - Package updater
  - Configuration manager
  - Resource monitor
  - Security guard
  - Backup agent
- Pre-configured task templates
  - Update packages
  - Cleanup temporary files
  - Check disk usage
  - Security updates
  - System health check
- Recommended model configurations
  - General purpose (llama3.2:3b)
  - Code generation (codellama:7b)
  - Small/lightweight (llama3.2:1b)
  - Large/complex tasks (llama3.1:8b)
- System monitoring with configurable thresholds
- Debian packaging support for easy installation
- Systemd service for background operation
- Desktop integration with .desktop file and icon
- Comprehensive documentation
  - README with quick start guide
  - Man pages
  - Contributing guidelines

### Security
- Sandboxed agent execution
- Configurable command blacklist
- Permission-based capabilities for agents
- Confirmation required for destructive operations

[Unreleased]: https://github.com/debai/debai/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/debai/debai/releases/tag/v1.0.0
