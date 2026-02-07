# Contributing to Botanu SDK

Thank you for your interest in contributing to Botanu SDK! This document provides guidelines and instructions for contributing.

## Developer Certificate of Origin (DCO)

This project requires all commits to be signed off in accordance with the [Developer Certificate of Origin (DCO)](https://developercertificate.org/). This certifies that you have the right to submit your contribution under the project's open source license.

To sign off your commits, add the `-s` flag to your git commit command:

```bash
git commit -s -m "Your commit message"
```

This will add a `Signed-off-by` line to your commit message:

```
Signed-off-by: Your Name <your.email@example.com>
```

If you've already made commits without signing off, you can amend them:

```bash
# Amend the last commit
git commit --amend -s

# Rebase and sign off multiple commits
git rebase --signoff HEAD~N  # where N is the number of commits
```

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/botanu-ai/botanu-sdk-python.git
   cd botanu-sdk-python
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. Run tests:
   ```bash
   pytest tests/
   ```

4. Run linting and type checks:
   ```bash
   ruff check src/ tests/
   ruff format src/ tests/
   mypy src/botanu/
   ```

## Pull Request Process

1. Fork the repository and create a feature branch
2. Make your changes with appropriate tests
3. Ensure all tests pass and linting is clean
4. Sign off all commits with DCO
5. Submit a pull request with a clear description

## Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints for all function signatures
- Write docstrings for public APIs
- Keep commits focused and atomic

## Reporting Issues

Please use GitHub Issues to report bugs or request features. Include:
- A clear description of the issue
- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Python version and OS

## Code of Conduct

This project follows the [LF Projects Code of Conduct](https://lfprojects.org/policies/code-of-conduct/).

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
