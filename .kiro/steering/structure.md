# Project Structure

This document outlines the organization and folder structure conventions for this project.

## Current Structure

```
.
├── .kiro/
│   ├── specs/          # Project specifications and requirements
│   └── steering/       # AI assistant guidance documents
```

## Recommended Structure Patterns

### General Guidelines

- Keep related files together in logical directories
- Use clear, descriptive folder names
- Separate source code from configuration and documentation
- Maintain a clean root directory

### Common Patterns by Project Type

#### Web Application

```
src/
├── components/         # Reusable UI components
├── pages/             # Page-level components
├── utils/             # Utility functions
├── hooks/             # Custom hooks (React)
├── services/          # API calls and external services
├── types/             # Type definitions
└── assets/            # Static assets
```

#### Backend API

```
src/
├── controllers/       # Request handlers
├── models/           # Data models
├── services/         # Business logic
├── middleware/       # Custom middleware
├── routes/           # Route definitions
├── utils/            # Utility functions
└── config/           # Configuration files
```

#### Library/Package

```
src/
├── lib/              # Main library code
├── types/            # Type definitions
└── utils/            # Utility functions
tests/                # Test files
docs/                 # Documentation
```

## File Naming Conventions

- Use kebab-case for directories and files when possible
- Use PascalCase for component files (React, Vue, etc.)
- Use descriptive names that indicate file purpose
- Group related files with consistent prefixes or suffixes

## Configuration Files

- Keep configuration files in the root or a dedicated `config/` directory
- Use environment-specific config files when needed
- Document configuration options and their purposes
