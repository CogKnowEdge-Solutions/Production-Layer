# Production-Layer

A production-ready layer for deploying and operating AI applications. This repository aggregates production-grade agentic projects — covering agentic workflows, multi-service orchestration, observability, and deployment — to take agentic ideas from prototype to production.

## Table of Contents

- [Features](#features)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Working with Sub-Repositories](#working-with-sub-repositories)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Agentic workflows** — production-grade agent orchestration and tool-calling.
- **Multi-service orchestration** — Docker Compose / Kubernetes-ready services.
- **Observability** — Prometheus + Grafana monitoring, logging, and tracing.
- **Deployment** — containerized, cloud-ready application layers.

## Repository Structure

This repository aggregates sub-projects using `git subtree`. Each sub-project lives in its own folder and retains its full git history.

```
Production-Layer/
└── CareMatch-Prototype/   # Prototype application
```

## Getting Started

Clone this repository and navigate into the sub-project you want to run:

```bash
git clone https://github.com/<org>/Production-Layer.git
cd Production-Layer
```

Each sub-project contains its own README with setup, configuration, and usage instructions.

## Working with Sub-Repositories

### Add a sub-repository

```bash
git subtree add --prefix=<Folder-Name> https://github.com/<org>/<repo>.git <branch>
```

### Fetch the latest changes from a sub-repository

```bash
git subtree pull --prefix=<Folder-Name> https://github.com/<org>/<repo>.git <branch>
```

### Extract a sub-repository into its own standalone repo

```bash
# Extract the folder's history into a temporary branch
git subtree split --prefix=<Folder-Name> -b <folder-name>-back

# Create a new repo and push the extracted history to it
mkdir <repo>.git && cd <repo>.git
git init
git remote add origin https://github.com/<org>/<new-repo>.git
git fetch <path-to-this-repo> <folder-name>-back
git checkout FETCH_HEAD
git push origin master
```

This preserves the complete commit history of the sub-project.

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request.

## License

[MIT](LICENSE)
