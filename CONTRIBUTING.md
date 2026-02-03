# Contributing to Qvantum Heat Pump Integration

Thank you for your interest in contributing to the Qvantum Heat Pump integration for Home Assistant! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Guidelines](#development-guidelines)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

This project follows the Home Assistant [Code of Conduct](https://www.home-assistant.io/code_of_conduct/). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

Key principles:

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the issue, not the person
- Help create a welcoming environment for all contributors

## Getting Started

### Prerequisites

- Home Assistant 2024.1.0 or newer
- Python 3.13 or newer
- Git
- A Qvantum heat pump for testing (or access to test credentials)

### Development Setup

1. **Fork and Clone**

   ```bash
   git fork https://github.com/majorfrog/qvantum-hass.git
   cd qvantum-hass
   ```

2. **Set Up Home Assistant Development Environment**
   - Follow [Home Assistant development documentation](https://developers.home-assistant.io/docs/development_environment)
   - Or use a development Home Assistant instance

3. **Link to Custom Components**

   ```bash
   # Create symlink in your HA config directory
   ln -s /path/to/qvantum-hass/custom_components/qvantum_hass \
         /path/to/homeassistant/config/custom_components/
   ```

4. **Restart Home Assistant**
   - The integration should now be available

## How to Contribute

### Reporting Bugs

When reporting bugs, please include:

1. **Clear Title**: Descriptive summary of the issue
2. **Environment**:
   - Home Assistant version
   - Integration version
   - Heat pump model
3. **Steps to Reproduce**: Detailed steps to recreate the issue
4. **Expected Behavior**: What should happen
5. **Actual Behavior**: What actually happens
6. **Logs**: Relevant log entries (with sensitive information removed)
7. **Screenshots**: If applicable

**Template**:

```markdown
**Describe the bug**
A clear and concise description of what the bug is.

**Environment**

- Home Assistant version: 2024.1.0
- Integration version: 1.0.0
- Heat pump model: Qvantum HP

**To Reproduce**
Steps to reproduce the behavior:

1. Go to '...'
2. Click on '....'
3. See error

**Expected behavior**
A clear description of what you expected to happen.

**Logs**
```

[Paste relevant log entries]

```

**Screenshots**
If applicable, add screenshots to help explain your problem.
```

### Suggesting Features

Feature requests are welcome! Please:

1. **Check Existing Issues**: Search for similar requests first
2. **Provide Context**: Explain the use case
3. **Be Specific**: Describe the desired behavior
4. **Consider Scope**: Ensure it aligns with the integration's purpose

**Template**:

```markdown
**Is your feature request related to a problem?**
A clear description of what the problem is. Ex. I'm always frustrated when [...]

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Other solutions or features you've considered.

**Additional context**
Any other context or screenshots about the feature request.
```

### Contributing Code

1. **Create a Feature Branch**

   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make Your Changes**
   - Follow the [Development Guidelines](#development-guidelines)
   - Add/update tests as needed
   - Update documentation

3. **Test Your Changes**
   - Test in a real Home Assistant instance
   - Verify existing functionality still works
   - Check logs for errors

4. **Commit Your Changes**

   ```bash
   git add .
   git commit -m "Add amazing feature"
   ```

5. **Push to Your Fork**

   ```bash
   git push origin feature/amazing-feature
   ```

6. **Open a Pull Request**
   - Provide a clear description
   - Reference related issues
   - Include testing notes

## Development Guidelines

### Code Style

- **Python**: Follow [PEP 8](https://pep8.org/) style guide
- **Type Hints**: Use type hints for all function arguments and return values
- **Docstrings**: Document all modules, classes, and functions using Google-style docstrings
- **Line Length**: Keep lines under 100 characters where reasonable
- **Naming**: Use descriptive variable and function names

**Example**:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qvantum sensor entities from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry for this integration instance
        async_add_entities: Callback to add entities to HA
    """
    # Implementation
```

### File Organization

- `__init__.py`: Integration setup and coordinator
- `const.py`: All constants and configuration
- `api.py`: API client implementation
- `config_flow.py`: Configuration flow
- `{platform}.py`: Platform-specific entity implementations
- `diagnostics.py`: Diagnostic data collection

### Documentation

- **Code Comments**: Explain "why" not "what"
- **Docstrings**: Required for all public functions/classes
- **README Updates**: Update README.md for user-facing changes
- **CHANGELOG**: Add entry to CHANGELOG.md

### Logging

Use appropriate log levels:

- `_LOGGER.debug()`: Detailed diagnostic information
- `_LOGGER.info()`: Informational messages
- `_LOGGER.warning()`: Warning messages
- `_LOGGER.error()`: Error messages
- `_LOGGER.exception()`: Error with stack trace

Never log sensitive information (passwords, tokens, etc.).

## Testing

### Manual Testing

1. **Install in Development Environment**
   - Link or copy to `custom_components/qvantum_hass`
   - Restart Home Assistant

2. **Test Configuration Flow**
   - Add integration through UI
   - Verify credential validation
   - Check device discovery

3. **Test Entity Creation**
   - Verify all expected entities are created
   - Check entity states and attributes
   - Test entity controls (switches, numbers, selects)

4. **Test Error Handling**
   - Test with invalid credentials
   - Test with offline device
   - Test API errors

5. **Check Logs**
   - Enable debug logging
   - Look for errors or warnings
   - Verify no sensitive data in logs

### Testing Checklist

Before submitting a PR, verify:

- [ ] Integration loads without errors
- [ ] Configuration flow works correctly
- [ ] All entities are created
- [ ] Entity states update correctly
- [ ] Controls (switches, numbers, selects) work
- [ ] Error handling works (try invalid credentials)
- [ ] Logs don't contain sensitive information
- [ ] No new warnings in Home Assistant logs
- [ ] Documentation is updated (if needed)
- [ ] CHANGELOG.md is updated

## Submitting Changes

### Pull Request Process

1. **Update Documentation**
   - Update README.md if user-facing changes
   - Update CHANGELOG.md with your changes
   - Add docstrings to new code

2. **Self-Review**
   - Review your own code first
   - Check for typos and formatting issues
   - Ensure code follows style guidelines
   - Remove debug/console statements

3. **Create Pull Request**
   - Use a descriptive title
   - Reference related issues (#123)
   - Describe what changed and why
   - Include testing notes
   - Add screenshots if relevant

4. **Address Review Comments**
   - Respond to all review comments
   - Make requested changes
   - Request re-review when ready

### Commit Messages

Write clear, descriptive commit messages:

**Good**:

```
Add support for cooling mode sensors

- Add cooling mode binary sensor
- Add cooling demand sensor
- Update entity registry with new sensors
- Add tests for cooling mode detection

Fixes #123
```

**Bad**:

```
fix stuff
```

### Branch Naming

Use descriptive branch names:

- `feature/add-cooling-support`
- `fix/sensor-availability-issue`
- `docs/improve-readme`
- `refactor/api-client-cleanup`

## Release Process

Releases are managed by project maintainers:

1. Update version in `manifest.json`
2. Update CHANGELOG.md with release date
3. Create GitHub release with tag
4. Release will be published to HACS

## Questions and Support

- **Development Questions**: Open a discussion on GitHub
- **Bug Reports**: Use GitHub issues
- **Feature Requests**: Use GitHub issues
- **Security Issues**: Contact maintainers privately

## Recognition

Contributors will be recognized in:

- GitHub contributors list
- CHANGELOG.md (for significant contributions)
- README.md credits section (for major features)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for helping improve the Qvantum Heat Pump integration!
