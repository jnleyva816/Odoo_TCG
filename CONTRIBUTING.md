# Contributing to TCG Inventory Management

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Odoo_TCG.git
   cd Odoo_TCG
   ```

3. **Set up development environment**:
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or: .\venv\Scripts\activate  # Windows

   # Install dependencies
   pip install -e ".[dev]"
   cd backend && pip install -e ".[dev]" && cd ..
   cd frontend && npm install && cd ..
   ```

4. **Install pre-commit hooks**:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Development Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write clean, readable code
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests**:
   ```bash
   # Backend tests
   cd backend
   pytest ../tests/ -v

   # Frontend build
   cd frontend
   npm run build
   ```

4. **Run linters**:
   ```bash
   # Backend
   cd backend
   ruff check app/
   ruff format app/
   mypy app/

   # Frontend
   cd frontend
   npm run lint
   ```

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

   **Commit Message Format**:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `style:` - Code style changes (formatting)
   - `refactor:` - Code refactoring
   - `test:` - Adding tests
   - `chore:` - Build process or tooling changes

6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request** on GitHub

## Code Style

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints for function signatures
- Write docstrings for public functions/classes
- Use `ruff` for linting and formatting
- Maximum line length: 100 characters

```python
def example_function(param: str, count: int = 0) -> dict[str, Any]:
    """Brief description of function.
    
    Args:
        param: Description of param
        count: Description of count
    
    Returns:
        Description of return value
    """
    return {"result": param * count}
```

### TypeScript/React (Frontend)

- Use TypeScript for type safety
- Follow React best practices
- Use functional components with hooks
- Use ESLint for linting
- Use Prettier for formatting

```typescript
interface Props {
  title: string;
  count?: number;
}

export function ExampleComponent({ title, count = 0 }: Props) {
  return <div>{title}: {count}</div>;
}
```

## Testing

### Backend Tests

- Write pytest tests in `tests/` directory
- Use fixtures for common setup
- Mock external dependencies (Odoo)
- Aim for >80% code coverage

```python
def test_example():
    """Test description."""
    result = my_function("input")
    assert result == "expected"
```

### Frontend Tests

- Test critical user flows
- Use React Testing Library
- Mock API calls

## Documentation

- Update README.md for user-facing changes
- Add docstrings/comments for complex code
- Update API documentation (OpenAPI schema)
- Add examples for new features

## Pull Request Guidelines

### Before Submitting

- ✅ Tests pass locally
- ✅ Linters pass (ruff, ESLint)
- ✅ Code is documented
- ✅ Commit messages follow convention
- ✅ Branch is up to date with main

### PR Description

Include:
- **What** - Description of changes
- **Why** - Motivation and context
- **How** - Technical approach
- **Testing** - How to test the changes
- **Screenshots** - For UI changes

### Review Process

1. Automated checks run (CI/CD)
2. Code review by maintainer
3. Address feedback
4. Approval and merge

## Reporting Bugs

**Before reporting**:
- Check existing issues
- Try latest version
- Gather reproduction steps

**Bug report should include**:
- Description of the bug
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (OS, Python version, Node version)
- Logs/screenshots

## Feature Requests

We welcome feature requests! Please:
- Check existing issues first
- Describe the use case
- Explain expected behavior
- Consider implementation approach

## Security

For security vulnerabilities:
- **DO NOT** open a public issue
- Email: joshleyva816@gmail.com
- See SECURITY.md for details

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Help others learn and grow

## Questions?

- Open a GitHub Discussion
- Ask in pull request comments
- Email: joshleyva816@gmail.com

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing! 🎉
