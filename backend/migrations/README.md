# Database Migrations

This directory contains database migration files managed by [Alembic](https://alembic.sqlalchemy.org/), the database migration tool for SQLAlchemy.

## Overview

The migration system allows you to:
- Version control your database schema changes
- Apply incremental updates to the database
- Rollback changes if needed
- Generate migrations automatically from model changes
- Maintain consistency across development, staging, and production environments

## Directory Structure

```
migrations/
├── README.md           # This file
├── env.py             # Alembic environment configuration
├── script.py.mako     # Template for generating migration files
└── versions/          # Directory containing migration files
    └── (migration files will be created here)
```

## Configuration

The migration system is configured to:
- Use the `DATABASE_URL` environment variable for database connection
- Import models from `models.orm` for autogenerate support
- Use the `Base.metadata` from `lib.database` as the target metadata
- Enable type and server default comparison for better change detection

## Usage

### Using Docker (Recommended)

From the project root directory, use the provided shell script:

```bash
# Check current migration status
./scripts/migrate.sh current

# View migration history
./scripts/migrate.sh history

# Create a new migration (manual)
./scripts/migrate.sh revision -m "Add users table"

# Create a new migration (autogenerate from model changes)
./scripts/migrate.sh revision --autogenerate -m "Add users table"

# Apply all pending migrations
./scripts/migrate.sh upgrade head

# Apply migrations up to a specific revision
./scripts/migrate.sh upgrade <revision_id>

# Rollback one migration
./scripts/migrate.sh downgrade -1

# Rollback to a specific revision
./scripts/migrate.sh downgrade <revision_id>

# Show details of a specific migration
./scripts/migrate.sh show <revision_id>
```

### Using Python Script (Inside Container)

From the backend directory inside the container:

```bash
# All the same commands as above, but using:
python scripts/migrate.py <command>
```

### Direct Alembic Commands (Inside Container)

```bash
# From the backend directory
alembic current
alembic history
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
```

## Common Workflows

### 1. Creating Your First Migration

After defining your SQLAlchemy models in `models/orm/`, create an initial migration:

```bash
./scripts/migrate.sh revision --autogenerate -m "Initial database schema"
```

This will:
- Analyze your models
- Compare with the current database state
- Generate a migration file with the necessary changes

### 2. Applying Migrations

To apply all pending migrations:

```bash
./scripts/migrate.sh upgrade head
```

### 3. Rolling Back Changes

To rollback the last migration:

```bash
./scripts/migrate.sh downgrade -1
```

To rollback to a specific revision:

```bash
./scripts/migrate.sh downgrade <revision_id>
```

### 4. Checking Migration Status

To see the current migration state:

```bash
./scripts/migrate.sh current
```

To see all migrations:

```bash
./scripts/migrate.sh history
```

## Best Practices

### 1. Always Review Generated Migrations

Even when using `--autogenerate`, always review the generated migration file before applying it:

1. Check that the changes match your intentions
2. Verify that data migrations are handled correctly
3. Ensure that the migration is reversible (has proper downgrade logic)

### 2. Test Migrations

Before applying migrations to production:

1. Test on a copy of production data
2. Verify that both upgrade and downgrade work correctly
3. Check that the migration doesn't cause data loss

### 3. Backup Before Major Changes

Always backup your database before applying migrations that:
- Drop tables or columns
- Modify data types
- Perform complex data transformations

### 4. Use Descriptive Messages

Use clear, descriptive messages for your migrations:

```bash
# Good
./scripts/migrate.sh revision --autogenerate -m "Add user authentication tables"

# Bad
./scripts/migrate.sh revision --autogenerate -m "Update"
```

### 5. Handle Data Migrations

For complex schema changes that require data migration:

1. Create the migration with `--autogenerate`
2. Edit the migration file to add data migration logic
3. Test thoroughly before applying

## Migration File Structure

Each migration file contains:

```python
"""Add user authentication tables

Revision ID: abc123
Revises: def456
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'abc123'
down_revision = 'def456'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Schema changes to apply
    pass

def downgrade() -> None:
    # Schema changes to rollback
    pass
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure all your models are properly imported in `models/orm/__init__.py`

2. **Connection Issues**: Verify that your `DATABASE_URL` environment variable is correct

3. **Permission Issues**: Ensure the database user has the necessary permissions to create/modify tables

4. **Autogenerate Not Detecting Changes**: 
   - Check that your models inherit from `Base`
   - Verify that models are imported in `env.py`
   - Ensure the database is up to date before generating

### Getting Help

- Check the [Alembic documentation](https://alembic.sqlalchemy.org/)
- Review the migration history: `./scripts/migrate.sh history`
- Check the current status: `./scripts/migrate.sh current`

## Environment Variables

The migration system uses the following environment variables:

- `DATABASE_URL`: PostgreSQL connection string (required)
- `PYTHONPATH`: Set automatically by the migration scripts

## Security Considerations

- Migration files may contain sensitive schema information
- Never commit database credentials to version control
- Use environment variables for database connections
- Review migrations for potential security implications

---

*For more information about the database schema, see `DATABASE_SCHEMA.md` in the backend directory.* 