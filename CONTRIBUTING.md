# Contributing to Debai

Thank you for your interest in contributing to Debai! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/manalejandro/debai/issues)
2. If not, create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - System information (OS, Python version, etc.)
   - Relevant logs or screenshots

### Suggesting Features

1. Check existing issues and discussions for similar suggestions
2. Create a new issue with:
   - Clear description of the feature
   - Use cases and benefits
   - Possible implementation approach

### Submitting Code

1. **Fork** the repository
2. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following our coding standards
4. **Write tests** for new functionality
5. **Run tests** to ensure everything passes:
   ```bash
   pytest tests/
   ```
6. **Commit** with clear messages:
   ```bash
   git commit -m "feat: add new agent template for network monitoring"
   ```
7. **Push** to your fork
8. **Create a Pull Request**

## Development Setup

### Prerequisites

- Python 3.10 or later
- GTK 4.0 and libadwaita 1.0
- Docker Engine from official Docker repository (for model testing)

### Setting Up

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/debai.git
cd debai

# Install Docker Engine from official repository (if not already installed)
# Add Docker's official GPG key
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker Engine
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=debai --cov-report=html

# Run specific test file
pytest tests/test_agent.py

# Run with verbose output
pytest -v
```

### Code Style

We use the following tools for code quality:

- **Black** for code formatting
- **isort** for import sorting
- **Ruff** for linting
- **mypy** for type checking

Run all checks:

```bash
# Format code
black src/
isort src/

# Lint
ruff check src/

# Type check
mypy src/
```

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(agent): add support for scheduled tasks
fix(gui): resolve memory leak in agent list
docs: update installation instructions
```

## Project Structure

```
debai/
├── src/debai/           # Main package
│   ├── core/            # Core business logic
│   │   ├── agent.py     # Agent management
│   │   ├── model.py     # Model management
│   │   ├── task.py      # Task management
│   │   └── system.py    # System utilities
│   ├── cli/             # Command-line interface
│   ├── gui/             # GTK4 graphical interface
│   └── generators/      # Image generators
├── tests/               # Test suite
├── docs/                # Documentation
├── data/                # Data files and resources
└── debian/              # Debian packaging
```

## Testing Guidelines

1. Write tests for all new functionality
2. Maintain or improve code coverage
3. Use meaningful test names
4. Group related tests in classes
5. Use fixtures for common setup

Example test:

```python
import pytest
from debai.core.agent import Agent, AgentConfig

class TestAgent:
    @pytest.fixture
    def agent_config(self):
        return AgentConfig(
            name="Test Agent",
            model_id="llama3.2:3b",
        )
    
    def test_agent_creation(self, agent_config):
        agent = Agent(agent_config)
        assert agent.name == "Test Agent"
        assert agent.status.value == "stopped"
    
    @pytest.mark.asyncio
    async def test_agent_start_stop(self, agent_config):
        agent = Agent(agent_config)
        # Test start/stop behavior
```

## Documentation

- Update docstrings for new/modified functions
- Use Google-style docstrings
- Update README.md for user-facing changes
- Add man page entries for new CLI commands

Example docstring:

```python
def create_agent(config: AgentConfig) -> Agent:
    """Create a new AI agent.
    
    Args:
        config: Configuration for the agent including name,
            type, and model settings.
    
    Returns:
        The newly created Agent instance.
    
    Raises:
        ValueError: If an agent with the same ID already exists.
    
    Example:
        >>> config = AgentConfig(name="My Agent", model_id="llama3.2:3b")
        >>> agent = create_agent(config)
    """
```

## Pull Request Process

1. Ensure all tests pass
2. Update documentation as needed
3. Add entry to CHANGELOG.md
4. Request review from maintainers
5. Address review feedback
6. Squash commits if requested

## Release Process

Maintainers follow this process for releases:

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create release tag
4. Build and publish packages
5. Update documentation

## Getting Help

- Open an issue for questions
- Join discussions on GitHub
- Check existing documentation

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 license.
