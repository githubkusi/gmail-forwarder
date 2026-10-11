# Project Instructions

## Removing Docker Volumes

When the user says "remove docker volumes", remove persistent Docker volumes belonging only to this project's Compose project.

- List the project's declared and existing Compose-labeled volumes first, and state that deleting them permanently removes their data.
- Remove only those exact project volumes. Never use `docker volume prune` or delete volumes belonging to other projects.
- If stopped containers hold the project volumes, remove only those project containers needed to release them.
- Verify that no volumes labeled for this Compose project remain.