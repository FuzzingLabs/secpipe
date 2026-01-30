## Description

<!-- Provide a brief description of the changes in this PR -->

## Type of Change

<!-- Mark the appropriate option with an 'x' -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🔧 Configuration change
- [ ] ♻️ Refactoring (no functional changes)
- [ ] 🎨 Style/formatting changes
- [ ] ✅ Test additions or updates

## Related Issues

<!-- Link to related issues using #issue_number -->
<!-- Example: Closes #123, Relates to #456 -->

## Changes Made

<!-- List the specific changes made in this PR -->

-
-
-

## Testing

<!-- Describe the tests you ran to verify your changes -->

### Tested Locally

- [ ] All tests pass (`pytest`, `uv build`, etc.)
- [ ] Linting passes (`ruff check`)
- [ ] Code builds successfully

### Worker Changes (if applicable)

- [ ] Docker images build successfully (`docker compose build`)
- [ ] Worker containers start correctly
- [ ] Tested with actual workflow execution

### Documentation

- [ ] Documentation updated (if needed)
- [ ] README updated (if needed)
- [ ] CHANGELOG.md updated (if user-facing changes)

## Pre-Merge Checklist

<!-- Ensure all items are completed before requesting review -->

- [ ] My code follows the project's coding standards
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

### Worker-Specific Checks (if workers/ modified)

- [ ] All worker files properly tracked by git (not gitignored)
- [ ] Worker validation script passes (`.github/scripts/validate-workers.sh`)
- [ ] Docker images build without errors
- [ ] Worker configuration updated in `docker-compose.yml` (if needed)

## Screenshots (if applicable)

<!-- Add screenshots to help explain your changes -->

## Additional Notes

<!-- Any additional information that reviewers should know -->
