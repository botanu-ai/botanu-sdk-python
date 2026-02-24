# Contributing to Botanu SDK

We welcome contributions of all kinds — bug fixes, new features, documentation
improvements, and more. This guide explains how to get started.

## Developer Certificate of Origin (DCO)

This project requires all commits to be signed off in accordance with the
[Developer Certificate of Origin (DCO)](https://developercertificate.org/).
The DCO certifies that you have the right to submit your contribution under the
project's open-source license.

To sign off your commits, add the `-s` flag:

```bash
git commit -s -m "Your commit message"
```

This adds a `Signed-off-by` line to your commit message:

```
Signed-off-by: Your Name <your.email@example.com>
```

If you have already made commits without signing off, you can amend them:

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

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

4. Run tests:
   ```bash
   pytest tests/
   ```

5. Run linting and type checks:
   ```bash
   ruff check src/ tests/
   ruff format src/ tests/
   mypy src/botanu/
   ```

## Pull Request Process

1. Fork the repository and create a feature branch from `main`
2. Make your changes with appropriate tests
3. Ensure all tests pass and linting is clean
4. Sign off all commits with DCO
5. Submit a pull request with a clear description of the change

Pull requests require approval from at least one [maintainer](./MAINTAINERS.md)
before merging.

## Finding Work

- Look for issues labelled
  [`good first issue`](https://github.com/botanu-ai/botanu-sdk-python/labels/good%20first%20issue)
  if you are new to the project
- Issues labelled
  [`help wanted`](https://github.com/botanu-ai/botanu-sdk-python/labels/help%20wanted)
  are ready for community contributions
- Join the discussion on
  [GitHub Discussions](https://github.com/botanu-ai/botanu-sdk-python/discussions)
  to ask questions or propose ideas

## Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints for all function signatures
- Write docstrings for public APIs
- Keep commits focused and atomic

## Reporting Issues

Please use [GitHub Issues](https://github.com/botanu-ai/botanu-sdk-python/issues)
to report bugs or request features. Include:

- A clear description of the issue
- Steps to reproduce (for bugs)
- Expected versus actual behaviour
- Python version and OS

## Code of Conduct

This project follows the
[LF Projects Code of Conduct](https://lfprojects.org/policies/code-of-conduct/).
See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](./LICENSE).
