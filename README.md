# Production-Layer

A production-ready layer for deploying and operating AI applications.

This repository aggregates the production-layer agentic projects: production-grade applications and prototypes built around agentic workflows, multi-service orchestration, observability, and deployment — everything needed to take agentic ideas from prototype to production.

## Repositories

This repository aggregates several sub-projects using `git subtree`. Each sub-project lives in its own folder and retains its full git history:

| Folder |
| --- |
| `CareMatch-Prototype/` |
| `CareMatch-SDD/` |

## Working with sub-repositories

### Add a sub-repository

```bash
git subtree add --prefix=<Folder-Name> https://github.com/<org>/<repo>.git <branch>
```

### Fetch the latest changes from a sub-repository

```bash
git subtree pull --prefix=<Folder-Name> https://github.com/<org>/<repo>.git <branch>
```

### Fetch a sub-repository back out into its own standalone repo

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

This preserves the complete commit history of that sub-project.

## License

[MIT](LICENSE)
