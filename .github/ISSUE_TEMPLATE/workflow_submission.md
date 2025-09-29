---
name: 🔄 Workflow Submission
about: Contribute a security workflow or module to the FuzzForge community
title: "[WORKFLOW] "
labels: workflow, community
assignees: ''
---

## Workflow Name
Provide a short, descriptive name for your workflow.

## Description
Explain what this workflow does and what security problems it solves.

## Category
What type of security workflow is this?

- [ ] 🛡️ **Security Assessment** - Static analysis, vulnerability scanning
- [ ] 🔍 **Secret Detection** - Credential and secret scanning
- [ ] 🎯 **Fuzzing** - Dynamic testing and fuzz testing
- [ ] 🔄 **Reverse Engineering** - Binary analysis and decompilation
- [ ] 🌐 **Infrastructure Security** - Container, cloud, network security
- [ ] 🔒 **Penetration Testing** - Offensive security testing
- [ ] 📋 **Other** - Please describe

## Files
Please attach or provide links to your workflow files:

- [ ] `workflow.py` - Main Prefect flow implementation
- [ ] `Dockerfile` - Container definition
- [ ] `metadata.yaml` - Workflow metadata
- [ ] Test files or examples
- [ ] Documentation

## Testing
How did you test this workflow? Please describe:

- **Test targets used**: (e.g., vulnerable_app, custom test cases)
- **Expected outputs**: (e.g., SARIF format, specific vulnerabilities detected)
- **Validation results**: (e.g., X vulnerabilities found, Y false positives)

## SARIF Compliance
- [ ] My workflow outputs results in SARIF format
- [ ] Results include severity levels and descriptions
- [ ] Code flow information is provided where applicable

## Security Guidelines
- [ ] This workflow focuses on **defensive security** purposes only
- [ ] I have not included any malicious tools or capabilities
- [ ] All secrets/credentials are parameterized (no hardcoded values)
- [ ] I have followed responsible disclosure practices

## Registry Integration
Have you updated the workflow registry?

- [ ] Added import statement to `backend/toolbox/workflows/registry.py`
- [ ] Added registry entry with proper metadata
- [ ] Tested workflow registration and deployment

## Additional Notes
Anything else the maintainers should know about this workflow?

---

🚀 **Thank you for contributing to FuzzForge!** Your workflow will help the security community automate and scale their testing efforts.

💬 **Questions?** Join our [Discord Community](https://discord.com/invite/acqv9FVG) to discuss your contribution!